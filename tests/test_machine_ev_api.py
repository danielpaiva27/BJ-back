from __future__ import annotations

import json
import math

import pytest
from fastapi.testclient import TestClient

from app.main import app
import app.routes.pre_round as pre_round_route_module
from blackjack_risk_engine.engine_core.pre_round.machine_ev import (
    MachineEvConfig,
    MachineEvInternalMetrics,
    MachineEvPublicSummary,
    MachineEvResult,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _valid_payload() -> dict[str, object]:
    return {
        "number_of_decks": 6,
        "seen_cards": [],
        "bankroll": 1000,
        "minimum_bet": 10,
        "rules": {
            "dealer_hits_soft_17": False,
            "blackjack_payout": 1.5,
            "surrender_allowed": False,
            "double_after_split": True,
        },
    }


def _fake_result(
    config: MachineEvConfig,
    *,
    timed_out: bool = False,
) -> MachineEvResult:
    warnings = (
        (
            "Machine EV exceeded configured duration budget; "
            "result remains exact but may be slow."
        ),
    ) if timed_out else ()
    return MachineEvResult(
        summary=MachineEvPublicSummary(
            estimated_next_hand_edge=0.05,
            risk_if_minimum_bet=0.01,
            minimum_bankroll_required_for_minimum_bet=400.0,
            recommendation_status="machine_ev_minimum_bet_within_risk_limit",
            recommendation_text=(
                "A aposta mínima fica dentro do limite aproximado de risco "
                "usando a vantagem estimada pela Machine EV."
            ),
        ),
        metrics=MachineEvInternalMetrics(
            states_evaluated=550,
            duration_ms=10.0,
            cache_hits=0,
            cache_misses=550,
            timed_out=timed_out,
            warnings=warnings,
        ),
        config=config,
        raw_ev_per_unit=0.05,
        variance_per_unit=1.3,
    )


def _all_keys(value: object):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from _all_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _all_keys(nested)


def test_machine_ev_endpoint_returns_minimal_public_response(
    client: TestClient,
) -> None:
    response = client.post(
        "/pre-round-analysis/machine-ev",
        json=_valid_payload(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_id"] == "machine_ev"
    assert payload["label"] == "Machine EV"
    assert payload["model_type"] == "composition_ev"
    assert payload["is_human_replicable"] is False
    assert math.isfinite(payload["estimated_next_hand_edge"])
    if payload["risk_if_minimum_bet"] is not None:
        assert math.isfinite(payload["risk_if_minimum_bet"])
        assert 0 <= payload["risk_if_minimum_bet"] <= 1
    required_bankroll = payload["minimum_bankroll_required_for_minimum_bet"]
    if required_bankroll is not None:
        assert math.isfinite(required_bankroll)
        assert required_bankroll >= 0
    assert payload["recommendation_status"]
    assert payload["recommendation_text"]
    assert "debug_metrics" not in payload


def test_default_response_excludes_internal_and_human_fields(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pre_round_route_module,
        "evaluate_machine_ev_pre_round",
        lambda machine_input, config: _fake_result(config),
    )

    response = client.post(
        "/pre-round-analysis/machine-ev",
        json=_valid_payload(),
    )

    assert response.status_code == 200
    keys = set(_all_keys(response.json()))
    assert keys.isdisjoint(
        {
            "running_count",
            "true_count",
            "betting_true_count",
            "ace_side_count",
            "scaled_running_count",
            "suggested_units",
            "suggested_amount",
            "states_evaluated",
            "duration_ms",
            "cache_hits",
            "cache_misses",
            "state_breakdown",
            "action_evs",
            "dealer_hole_card",
        }
    )


def test_debug_metrics_are_opt_in(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pre_round_route_module,
        "evaluate_machine_ev_pre_round",
        lambda machine_input, config: _fake_result(config),
    )
    payload = _valid_payload()
    payload["include_debug_metrics"] = True

    response = client.post(
        "/pre-round-analysis/machine-ev",
        json=payload,
    )

    assert response.status_code == 200
    debug = response.json()["debug_metrics"]
    assert debug["states_evaluated"] == 550
    assert debug["duration_ms"] == 10.0
    assert debug["cache_hits"] == 0
    assert debug["cache_misses"] == 550
    assert debug["timed_out"] is False
    assert debug["warnings"] == []
    assert debug["precision_mode"].startswith("exact_observable_initial_states")
    assert "dealer_hole_card" not in set(_all_keys(debug))
    assert "state_breakdown" not in debug


def test_custom_duration_budget_is_propagated_and_debugged(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_evaluate(machine_input, config):
        captured["config"] = config
        return _fake_result(config, timed_out=True)

    monkeypatch.setattr(
        pre_round_route_module,
        "evaluate_machine_ev_pre_round",
        fake_evaluate,
    )
    payload = _valid_payload()
    payload.update(
        {
            "include_debug_metrics": True,
            "max_duration_ms": 1,
        }
    )

    response = client.post(
        "/pre-round-analysis/machine-ev",
        json=payload,
    )

    assert response.status_code == 200
    assert math.isfinite(response.json()["estimated_next_hand_edge"])
    assert captured["config"].max_duration_ms == 1
    assert response.json()["debug_metrics"]["timed_out"] is True
    assert any(
        "duration budget" in warning
        for warning in response.json()["debug_metrics"]["warnings"]
    )


def test_custom_engine_mode_is_propagated(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_evaluate(machine_input, config):
        captured["config"] = config
        return _fake_result(config)

    monkeypatch.setattr(
        pre_round_route_module,
        "evaluate_machine_ev_pre_round",
        fake_evaluate,
    )
    payload = _valid_payload()
    payload["engine_mode"] = "hybrid"

    response = client.post(
        "/pre-round-analysis/machine-ev",
        json=payload,
    )

    assert response.status_code == 200
    assert captured["config"].decision_engine_mode == "hybrid"


def test_invalid_engine_mode_returns_422(client: TestClient) -> None:
    payload = _valid_payload()
    payload["engine_mode"] = "banana"

    response = client.post(
        "/pre-round-analysis/machine-ev",
        json=payload,
    )

    assert response.status_code == 422
    assert "engine_mode" in response.text


def test_seen_cards_scenarios_return_finite_results(
    client: TestClient,
) -> None:
    neutral = _valid_payload()
    neutral["number_of_decks"] = 1
    rich = _valid_payload()
    rich["number_of_decks"] = 1
    rich["seen_cards"] = [
        rank
        for rank in ("2", "3", "4", "5", "6")
        for _ in range(4)
    ]

    neutral_response = client.post(
        "/pre-round-analysis/machine-ev",
        json=neutral,
    )
    rich_response = client.post(
        "/pre-round-analysis/machine-ev",
        json=rich,
    )

    assert neutral_response.status_code == 200
    assert rich_response.status_code == 200
    assert math.isfinite(neutral_response.json()["estimated_next_hand_edge"])
    assert math.isfinite(rich_response.json()["estimated_next_hand_edge"])


def test_six_to_five_endpoint_ev_does_not_exceed_three_to_two(
    client: TestClient,
) -> None:
    seen_cards = [
        rank
        for rank in ("2", "3", "4", "5", "6")
        for _ in range(12)
    ]
    three_to_two = _valid_payload()
    three_to_two["seen_cards"] = seen_cards
    six_to_five = _valid_payload()
    six_to_five["seen_cards"] = seen_cards
    six_to_five["rules"] = {
        **six_to_five["rules"],
        "blackjack_payout": 1.2,
    }

    standard_response = client.post(
        "/pre-round-analysis/machine-ev",
        json=three_to_two,
    )
    reduced_payout_response = client.post(
        "/pre-round-analysis/machine-ev",
        json=six_to_five,
    )

    assert standard_response.status_code == 200
    assert reduced_payout_response.status_code == 200
    standard_payload = standard_response.json()
    reduced_payout_payload = reduced_payout_response.json()
    assert reduced_payout_payload["estimated_next_hand_edge"] <= (
        standard_payload["estimated_next_hand_edge"] + 1e-9
    )
    assert "debug_metrics" not in standard_payload
    assert "debug_metrics" not in reduced_payout_payload
    for payload in (standard_payload, reduced_payout_payload):
        keys = set(_all_keys(payload))
        assert "dealer_hole_card" not in keys
        assert "suggested_units" not in keys
        assert "suggested_amount" not in keys


def test_less_than_three_cards_remaining_returns_clear_422(
    client: TestClient,
) -> None:
    full_shoe = (
        ["A"] * 4
        + ["2"] * 4
        + ["3"] * 4
        + ["4"] * 4
        + ["5"] * 4
        + ["6"] * 4
        + ["7"] * 4
        + ["8"] * 4
        + ["9"] * 4
        + ["10"] * 16
    )
    cards_left = ["A", "10"]
    for card in cards_left:
        full_shoe.remove(card)
    payload = _valid_payload()
    payload["number_of_decks"] = 1
    payload["seen_cards"] = full_shoe

    response = client.post(
        "/pre-round-analysis/machine-ev",
        json=payload,
    )

    assert response.status_code == 422
    assert "At least 3 cards" in response.json()["detail"]


def test_invalid_card_returns_422(client: TestClient) -> None:
    payload = _valid_payload()
    payload["seen_cards"] = ["X"]

    response = client.post(
        "/pre-round-analysis/machine-ev",
        json=payload,
    )

    assert response.status_code == 422
    assert "seen_cards" in response.text


@pytest.mark.parametrize("minimum_bet", [0, -1])
def test_invalid_minimum_bet_returns_422(
    client: TestClient,
    minimum_bet: float,
) -> None:
    payload = _valid_payload()
    payload["minimum_bet"] = minimum_bet

    response = client.post(
        "/pre-round-analysis/machine-ev",
        json=payload,
    )

    assert response.status_code == 422
    assert "minimum_bet" in response.text


def test_human_pre_round_endpoint_remains_three_systems(
    client: TestClient,
) -> None:
    response = client.post(
        "/pre-round-analysis",
        json={
            "number_of_decks": 6,
            "seen_cards": [],
            "bankroll": 1000,
            "minimum_bet": 10,
        },
    )

    assert response.status_code == 200
    assert [
        system["system_id"]
        for system in response.json()["systems"]
    ] == ["hi_lo", "hi_opt_ii", "wong_halves"]


def test_response_contains_no_hole_card_or_prohibited_language(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pre_round_route_module,
        "evaluate_machine_ev_pre_round",
        lambda machine_input, config: _fake_result(config),
    )

    response = client.post(
        "/pre-round-analysis/machine-ev",
        json=_valid_payload(),
    )

    assert response.status_code == 200
    serialized = json.dumps(response.json(), ensure_ascii=False).lower()
    assert "dealer_hole_card" not in serialized
    for forbidden in ("garantido", "segura", "certeza", "vencer o cassino"):
        assert forbidden not in serialized


def test_machine_ev_endpoint_is_documented_in_openapi(
    client: TestClient,
) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    operation = response.json()["paths"][
        "/pre-round-analysis/machine-ev"
    ]["post"]
    assert "pre-round" in operation["tags"]
    assert operation["requestBody"]["required"] is True
