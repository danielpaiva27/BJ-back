from __future__ import annotations

import json
import math

import pytest
from fastapi.testclient import TestClient
import blackjack_risk_engine.engine_core.pre_round.analysis as pre_round_analysis_module

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _valid_payload() -> dict[str, object]:
    return {
        "number_of_decks": 6,
        "seen_cards": ["2", "5", "10", "A"],
        "bankroll": 1000,
        "minimum_bet": 10,
        "rules": {
            "dealer_hits_soft_17": False,
            "blackjack_payout": "3:2",
            "double_after_split": True,
            "surrender_allowed": False,
            "dealer_peek": True,
        },
    }


def _system(payload: dict[str, object], system_id: str) -> dict[str, object]:
    systems = payload["systems"]
    assert isinstance(systems, list)
    return next(system for system in systems if system["system_id"] == system_id)


def test_valid_payload_returns_all_systems_and_policy(
    client: TestClient,
) -> None:
    response = client.post("/pre-round-analysis", json=_valid_payload())

    assert response.status_code == 200
    payload = response.json()
    assert [system["system_id"] for system in payload["systems"]] == [
        "hi_lo",
        "hi_opt_ii",
        "wong_halves",
    ]
    assert payload["policy"]["policy_id"] == "risk_capped_growth"
    assert payload["policy"]["risk_of_ruin_limit"] == 0.05
    assert payload["policy"]["max_single_round_exposure"] == 0.05
    assert payload["most_favorable_estimate_system_id"] in {
        "hi_lo",
        "hi_opt_ii",
        "wong_halves",
    }


def test_omitted_systems_returns_all_three(client: TestClient) -> None:
    payload = _valid_payload()
    payload.pop("systems", None)

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 200
    assert len(response.json()["systems"]) == 3


def test_hi_lo_filter_returns_only_hi_lo(client: TestClient) -> None:
    payload = _valid_payload()
    payload["systems"] = ["HI_LO"]

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 200
    assert [
        system["system_id"] for system in response.json()["systems"]
    ] == ["hi_lo"]


def test_hi_opt_ii_response_includes_ace_side_count(
    client: TestClient,
) -> None:
    payload = _valid_payload()
    payload["systems"] = ["hi_opt_ii"]

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 200
    hi_opt = response.json()["systems"][0]
    assert hi_opt["system_id"] == "hi_opt_ii"
    assert "ace_side_count" in hi_opt
    assert "playing_true_count" in hi_opt
    assert "betting_true_count" in hi_opt
    assert "betting_running_count" in hi_opt
    assert "scaled_running_count" not in hi_opt


def test_wong_halves_response_preserves_scaled_count(
    client: TestClient,
) -> None:
    payload = _valid_payload()
    payload["seen_cards"] = ["2", "5", "9", "10", "A"]
    payload["systems"] = ["wong_halves"]

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 200
    wong_halves = response.json()["systems"][0]
    assert wong_halves["system_id"] == "wong_halves"
    assert wong_halves["scaled_running_count"] == -1
    assert wong_halves["scale"] == 2
    assert "ace_side_count" not in wong_halves


def test_response_includes_risk_capped_policy_fields(
    client: TestClient,
) -> None:
    payload = _valid_payload()
    payload["seen_cards"] = ["2"] * 20 + ["3"] * 20 + ["4"] * 20

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 200
    for system in response.json()["systems"]:
        for field in (
            "estimated_risk_of_ruin",
            "risk_of_ruin_limit",
            "risk_model",
            "variance_per_unit",
            "max_bet_by_risk",
            "max_single_round_exposure",
            "max_bet_by_exposure",
            "selected_bet_fraction",
            "kelly_fraction",
            "risk_limited_fraction",
            "minimum_bet_exceeds_risk_cap",
        ):
            assert field in system
        for optional_field in (
            "risk_if_minimum_bet",
            "minimum_bankroll_required_for_minimum_bet",
        ):
            optional_value = system.get(optional_field)
            if optional_value is not None:
                assert isinstance(optional_value, (int, float))
                assert math.isfinite(optional_value)
        if system["suggested_amount"] > 0:
            assert (
                system["estimated_risk_of_ruin"]
                <= system["risk_of_ruin_limit"]
            )


def test_positive_edge_minimum_bet_exceeds_risk_cap_status_and_fields(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pre_round_analysis_module,
        "estimate_player_edge",
        lambda **_: 0.0196,
    )

    payload = _valid_payload()
    payload["seen_cards"] = []
    payload["bankroll"] = 200
    payload["minimum_bet"] = 5

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 200
    body = response.json()
    expected_max_bet_by_risk = (2 * 0.0196 * 200) / (1.3 * math.log(1 / 0.05))
    expected_minimum_bankroll_required = (1.3 * 5 * math.log(1 / 0.05)) / (
        2 * 0.0196
    )
    for system in body["systems"]:
        assert system["recommendation_status"] == (
            "positive_edge_minimum_bet_exceeds_risk_cap"
        )
        assert system["suggested_units"] == 0
        assert system["suggested_amount"] == 0
        assert system["minimum_bet_exceeds_risk_cap"] is True
        assert system["max_bet_by_risk"] == pytest.approx(expected_max_bet_by_risk)
        assert system["risk_if_minimum_bet"] > 0.05
        assert system[
            "minimum_bankroll_required_for_minimum_bet"
        ] == pytest.approx(expected_minimum_bankroll_required)

    serialized = json.dumps(body, ensure_ascii=False).lower()
    assert "nan" not in serialized
    assert "infinity" not in serialized


def test_invalid_card_returns_422(client: TestClient) -> None:
    payload = _valid_payload()
    payload["seen_cards"] = ["X"]

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 422
    assert "seen_cards" in response.text


def test_too_many_aces_returns_clear_422(client: TestClient) -> None:
    payload = _valid_payload()
    payload["number_of_decks"] = 1
    payload["seen_cards"] = ["A"] * 5

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 422
    assert "5 copies of A" in response.json()["detail"]


def test_too_many_tens_returns_clear_422(client: TestClient) -> None:
    payload = _valid_payload()
    payload["number_of_decks"] = 1
    payload["seen_cards"] = ["10"] * 17

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 422
    assert "17 copies of 10" in response.json()["detail"]


def test_unknown_system_returns_clear_422(client: TestClient) -> None:
    payload = _valid_payload()
    payload["systems"] = ["banana_count"]

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 422
    assert "unknown count system 'banana_count'" in response.json()["detail"]


def test_empty_systems_returns_clear_422(client: TestClient) -> None:
    payload = _valid_payload()
    payload["systems"] = []

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "At least one counting system must be provided."
    )


def test_insufficient_bankroll_is_returned_by_every_system(
    client: TestClient,
) -> None:
    payload = _valid_payload()
    payload["bankroll"] = 5
    payload["minimum_bet"] = 10

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 200
    for system in response.json()["systems"]:
        assert system["recommendation_status"] == "insufficient_bankroll"
        assert system["suggested_units"] == 0


def test_neutral_shoe_returns_observe(client: TestClient) -> None:
    payload = _valid_payload()
    payload["seen_cards"] = []
    payload["rules"] = {
        "blackjack_payout": "3:2",
        "double_after_split": False,
    }

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 200
    for system in response.json()["systems"]:
        assert system["estimated_player_edge"] < 0
        assert system["recommendation_status"] == "observe"


def test_six_to_five_worsens_edge_for_same_shoe(
    client: TestClient,
) -> None:
    three_to_two = _valid_payload()
    three_to_two["systems"] = ["hi_lo"]
    three_to_two["rules"]["blackjack_payout"] = "3:2"
    six_to_five = _valid_payload()
    six_to_five["systems"] = ["hi_lo"]
    six_to_five["rules"]["blackjack_payout"] = "6:5"

    standard_response = client.post(
        "/pre-round-analysis",
        json=three_to_two,
    )
    six_to_five_response = client.post(
        "/pre-round-analysis",
        json=six_to_five,
    )

    assert standard_response.status_code == 200
    assert six_to_five_response.status_code == 200
    standard_edge = _system(
        standard_response.json(),
        "hi_lo",
    )["estimated_player_edge"]
    six_to_five_edge = _system(
        six_to_five_response.json(),
        "hi_lo",
    )["estimated_player_edge"]
    assert six_to_five_edge < standard_edge


def test_response_contains_no_risk_profile_language(
    client: TestClient,
) -> None:
    response = client.post("/pre-round-analysis", json=_valid_payload())

    assert response.status_code == 200
    serialized = json.dumps(response.json(), ensure_ascii=False).lower()
    for forbidden in (
        "risk_profile",
        "conservative",
        "moderate",
        "aggressive",
        "conservador",
        "moderado",
        "agressivo",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("number_of_decks", 0),
        ("bankroll", "NaN"),
        ("minimum_bet", "Infinity"),
    ],
)
def test_invalid_numeric_request_fields_return_422(
    client: TestClient,
    field: str,
    value: object,
) -> None:
    payload = _valid_payload()
    payload[field] = value

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "required_field",
    ["number_of_decks", "seen_cards", "bankroll", "minimum_bet"],
)
def test_required_request_fields_return_422_when_missing(
    client: TestClient,
    required_field: str,
) -> None:
    payload = _valid_payload()
    payload.pop(required_field)

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 422


def test_number_of_decks_rejects_boolean(client: TestClient) -> None:
    payload = _valid_payload()
    payload["number_of_decks"] = True

    response = client.post("/pre-round-analysis", json=payload)

    assert response.status_code == 422


def test_endpoint_is_documented_in_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    operation = response.json()["paths"]["/pre-round-analysis"]["post"]
    assert "pre-round" in operation["tags"]
    assert operation["requestBody"]["required"] is True


def test_existing_analyze_hand_endpoint_still_works(
    client: TestClient,
) -> None:
    response = client.post(
        "/analyze-hand",
        json={
            "player_hand": ["10", "6"],
            "dealer_upcard": "10",
            "seen_cards": ["2", "5", "6", "A", "10"],
            "rules": {
                "number_of_decks": 6,
                "dealer_hits_soft_17": False,
                "blackjack_payout": "3:2",
                "double_allowed": True,
                "double_after_split": True,
                "surrender_allowed": False,
                "max_splits": 3,
                "dealer_peek": True,
            },
            "simulations": 10,
            "seed": 42,
            "bankroll": 1000,
            "minimum_bet": 10,
            "risk_profile": "moderate",
        },
    )

    assert response.status_code == 200
    assert "recommendation" in response.json()
