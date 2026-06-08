import math
from types import SimpleNamespace

import pytest

from blackjack_risk_engine.engine_core.pre_round import (
    BASE_HOUSE_EDGE,
    BLACKJACK_SIX_TO_FIVE_PENALTY,
    DEALER_HITS_SOFT_17_PENALTY,
    DOUBLE_AFTER_SPLIT_BENEFIT,
    SURRENDER_ALLOWED_BENEFIT,
    estimate_player_edge,
)


@pytest.mark.parametrize(
    ("betting_true_count", "expected_edge"),
    [
        (0, -0.005),
        (1, 0.0),
        (2, 0.005),
    ],
)
def test_standard_true_count_edge_estimates(
    betting_true_count: float,
    expected_edge: float,
) -> None:
    assert estimate_player_edge(betting_true_count) == pytest.approx(expected_edge)


@pytest.mark.parametrize("payout", ["6:5", "6 / 5", 1.2, "1.2"])
def test_six_to_five_blackjack_payout_worsens_edge(payout: object) -> None:
    edge = estimate_player_edge(0, rules={"blackjack_payout": payout})

    assert edge == pytest.approx(
        -(BASE_HOUSE_EDGE + BLACKJACK_SIX_TO_FIVE_PENALTY)
    )


def test_blackjack_payout_multiplier_is_supported_on_rule_objects() -> None:
    rules = SimpleNamespace(blackjack_payout_multiplier=1.2)

    assert estimate_player_edge(0, rules=rules) == pytest.approx(-0.019)


def test_unknown_blackjack_payout_uses_standard_baseline() -> None:
    assert estimate_player_edge(
        0,
        rules={"blackjack_payout": "unknown"},
    ) == pytest.approx(-BASE_HOUSE_EDGE)


def test_dealer_hits_soft_17_worsens_edge() -> None:
    edge = estimate_player_edge(0, rules={"dealer_hits_soft_17": True})

    assert edge == pytest.approx(
        -(BASE_HOUSE_EDGE + DEALER_HITS_SOFT_17_PENALTY)
    )


def test_surrender_allowed_improves_edge() -> None:
    edge = estimate_player_edge(0, rules={"surrender_allowed": True})

    assert edge == pytest.approx(
        -(BASE_HOUSE_EDGE - SURRENDER_ALLOWED_BENEFIT)
    )


def test_double_after_split_improves_edge() -> None:
    rules = SimpleNamespace(double_after_split=True)

    assert estimate_player_edge(0, rules=rules) == pytest.approx(
        -(BASE_HOUSE_EDGE - DOUBLE_AFTER_SPLIT_BENEFIT)
    )


def test_rule_adjustments_are_combined() -> None:
    rules = {
        "blackjack_payout": "6:5",
        "dealer_hits_soft_17": True,
        "surrender_allowed": True,
        "double_after_split": True,
        "dealer_peek": False,
    }
    adjusted_house_edge = (
        BASE_HOUSE_EDGE
        + BLACKJACK_SIX_TO_FIVE_PENALTY
        + DEALER_HITS_SOFT_17_PENALTY
        - SURRENDER_ALLOWED_BENEFIT
        - DOUBLE_AFTER_SPLIT_BENEFIT
    )

    assert estimate_player_edge(3, rules=rules) == pytest.approx(
        0.015 - adjusted_house_edge
    )


@pytest.mark.parametrize("invalid_true_count", [math.nan, math.inf, -math.inf])
def test_non_finite_true_count_raises_clear_error(
    invalid_true_count: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="betting_true_count must be a finite number",
    ):
        estimate_player_edge(invalid_true_count)


@pytest.mark.parametrize("invalid_true_count", ["2", None, True])
def test_non_numeric_true_count_raises_clear_error(
    invalid_true_count: object,
) -> None:
    with pytest.raises(
        ValueError,
        match="betting_true_count must be a finite number",
    ):
        estimate_player_edge(invalid_true_count)  # type: ignore[arg-type]


def test_estimated_edge_is_always_finite_for_finite_input() -> None:
    assert math.isfinite(estimate_player_edge(1e100))
