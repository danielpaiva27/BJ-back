from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

from app.main import app
from blackjack_risk_engine.engine_core import (
    action_ev,
    deterministic_analysis,
    hybrid_analysis,
    monte_carlo_analysis,
)


def _analyze_hand_payload() -> dict[str, object]:
    return {
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
        "engine_mode": "deterministic",
        "simulations": 100,
        "seed": 42,
        "bankroll": 1000,
        "minimum_bet": 10,
        "risk_profile": "moderate",
    }


def _pre_round_payload() -> dict[str, object]:
    return {
        "number_of_decks": 6,
        "seen_cards": ["2", "5", "6", "A", "10"],
        "bankroll": 1000,
        "minimum_bet": 10,
        "rules": {
            "blackjack_payout": "3:2",
            "dealer_hits_soft_17": False,
            "double_after_split": True,
            "surrender_allowed": False,
            "dealer_peek": True,
        },
    }


def test_pre_round_call_does_not_change_hand_decision() -> None:
    client = TestClient(app)

    before = client.post("/analyze-hand", json=_analyze_hand_payload())
    pre_round = client.post(
        "/pre-round-analysis",
        json=_pre_round_payload(),
    )
    after = client.post("/analyze-hand", json=_analyze_hand_payload())

    assert before.status_code == 200
    assert pre_round.status_code == 200
    assert after.status_code == 200

    before_payload = before.json()
    after_payload = after.json()
    for field in (
        "input",
        "rules",
        "hand_analysis",
        "counting",
        "actions",
        "recommendation",
        "betting",
    ):
        assert after_payload[field] == before_payload[field]


def test_pre_round_snapshot_field_does_not_change_hand_decision() -> None:
    client = TestClient(app)
    baseline = client.post("/analyze-hand", json=_analyze_hand_payload())
    payload_with_snapshot = _analyze_hand_payload()
    payload_with_snapshot["pre_round_analysis"] = client.post(
        "/pre-round-analysis",
        json=_pre_round_payload(),
    ).json()

    response = client.post("/analyze-hand", json=payload_with_snapshot)

    assert baseline.status_code == 200
    assert response.status_code == 200
    assert response.json()["actions"] == baseline.json()["actions"]
    assert (
        response.json()["recommendation"]
        == baseline.json()["recommendation"]
    )


def test_decision_modules_do_not_import_pre_round_counting_layer() -> None:
    for module in (
        action_ev,
        deterministic_analysis,
        hybrid_analysis,
        monte_carlo_analysis,
    ):
        source = inspect.getsource(module)
        assert "engine_core.pre_round" not in source
        assert "engine_core.counting" not in source
        assert "betting_true_count" not in source
        assert "hi_opt_ii" not in source
        assert "wong_halves" not in source
