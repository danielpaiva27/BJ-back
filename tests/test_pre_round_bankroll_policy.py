import math

import pytest

from blackjack_risk_engine.engine_core.pre_round import (
    MAX_BANKROLL_EXPOSURE,
    MAX_SINGLE_ROUND_EXPOSURE,
    POLICY_ID,
    RISK_MODEL,
    RISK_OF_RUIN_LIMIT,
    VARIANCE_PER_UNIT,
    calculate_minimum_bankroll_for_bet_at_risk_limit,
    calculate_max_bet_for_risk_limit,
    estimate_risk_of_ruin,
    get_bankroll_policy_info,
    suggest_bankroll_exposure,
)


@pytest.mark.parametrize("edge", [-0.005, 0.0])
def test_non_positive_edge_recommends_observing(edge: float) -> None:
    result = suggest_bankroll_exposure(
        bankroll=1000,
        minimum_bet=10,
        estimated_player_edge=edge,
    )

    assert result["should_enter"] is False
    assert result["suggested_units"] == 0
    assert result["suggested_amount"] == 0
    assert result["estimated_risk_of_ruin"] == 0
    assert result["recommendation_status"] == "observe"
    assert result["risk_if_minimum_bet"] is None
    assert result["minimum_bankroll_required_for_minimum_bet"] is None
    assert result["minimum_bet_exceeds_risk_cap"] is False


@pytest.mark.parametrize("bankroll", [0, -1, math.nan, math.inf, "1000"])
def test_invalid_bankroll_returns_objective_status(bankroll: object) -> None:
    result = suggest_bankroll_exposure(
        bankroll=bankroll,  # type: ignore[arg-type]
        minimum_bet=10,
        estimated_player_edge=0.05,
    )

    assert result["should_enter"] is False
    assert result["recommendation_status"] == "invalid_bankroll"
    assert result["suggested_units"] == 0
    assert result["suggested_amount"] == 0


@pytest.mark.parametrize("minimum_bet", [0, -1, math.nan, math.inf, "10"])
def test_invalid_minimum_bet_returns_objective_status(
    minimum_bet: object,
) -> None:
    result = suggest_bankroll_exposure(
        bankroll=1000,
        minimum_bet=minimum_bet,  # type: ignore[arg-type]
        estimated_player_edge=0.05,
    )

    assert result["should_enter"] is False
    assert result["recommendation_status"] == "invalid_minimum_bet"
    assert result["suggested_units"] == 0
    assert result["suggested_amount"] == 0


def test_bankroll_below_minimum_bet_is_insufficient() -> None:
    result = suggest_bankroll_exposure(
        bankroll=5,
        minimum_bet=10,
        estimated_player_edge=0.05,
    )

    assert result["should_enter"] is False
    assert result["recommendation_status"] == "insufficient_bankroll"


def test_edge_five_percent_recommends_two_units_within_risk_limit() -> None:
    result = suggest_bankroll_exposure(
        bankroll=1000,
        minimum_bet=10,
        estimated_player_edge=0.05,
    )

    expected_max_bet_by_risk = (
        2 * 0.05 * 1000
    ) / (VARIANCE_PER_UNIT * math.log(1 / RISK_OF_RUIN_LIMIT))
    expected_risk = math.exp(
        (-2 * 0.05 * 1000) / (VARIANCE_PER_UNIT * 20)
    )

    assert result["should_enter"] is True
    assert result["max_bet_by_risk"] == pytest.approx(expected_max_bet_by_risk)
    assert result["max_bet_by_exposure"] == pytest.approx(50)
    assert result["suggested_units"] == 2
    assert result["suggested_amount"] == 20
    assert result["estimated_risk_of_ruin"] == pytest.approx(expected_risk)
    assert result["estimated_risk_of_ruin"] <= RISK_OF_RUIN_LIMIT
    assert result["risk_if_minimum_bet"] <= RISK_OF_RUIN_LIMIT
    assert result["minimum_bet_exceeds_risk_cap"] is False
    assert result["recommendation_status"] == "favorable_risk_capped"


def test_edge_six_percent_recommends_exposure_within_risk_limit() -> None:
    result = suggest_bankroll_exposure(
        bankroll=1000,
        minimum_bet=10,
        estimated_player_edge=0.06,
    )

    assert result["should_enter"] is True
    assert result["suggested_units"] >= 1
    assert result["estimated_risk_of_ruin"] <= RISK_OF_RUIN_LIMIT


def test_positive_edge_minimum_bet_exceeds_risk_cap_real_world_case() -> None:
    result = suggest_bankroll_exposure(
        bankroll=200,
        minimum_bet=5,
        estimated_player_edge=0.0196,
    )

    assert result["should_enter"] is False
    assert result["suggested_units"] == 0
    assert result["suggested_amount"] == 0
    assert result["recommendation_status"] == (
        "positive_edge_minimum_bet_exceeds_risk_cap"
    )
    expected_max_bet_by_risk = (
        2 * 0.0196 * 200
    ) / (VARIANCE_PER_UNIT * math.log(1 / RISK_OF_RUIN_LIMIT))
    expected_minimum_bankroll_required = (
        VARIANCE_PER_UNIT * 5 * math.log(1 / RISK_OF_RUIN_LIMIT)
    ) / (2 * 0.0196)
    expected_risk_if_minimum_bet = math.exp(
        (-2 * 0.0196 * 200) / (VARIANCE_PER_UNIT * 5)
    )

    assert result["max_bet_by_risk"] == pytest.approx(expected_max_bet_by_risk)
    assert result["risk_if_minimum_bet"] == pytest.approx(expected_risk_if_minimum_bet)
    assert result["risk_if_minimum_bet"] > 0.05
    assert result["minimum_bet_exceeds_risk_cap"] is True
    assert result[
        "minimum_bankroll_required_for_minimum_bet"
    ] == pytest.approx(expected_minimum_bankroll_required)
    assert "menor aposta possivel" in result["recommendation_text"].lower()


def test_small_positive_edge_can_remain_marginal_observe() -> None:
    result = suggest_bankroll_exposure(
        bankroll=1000,
        minimum_bet=10,
        estimated_player_edge=0.05,
        max_single_round_exposure=0.005,
    )

    assert result["should_enter"] is False
    assert result["suggested_units"] == 0
    assert result["estimated_risk_of_ruin"] == 0
    assert result["minimum_bet_exceeds_risk_cap"] is False
    assert result["recommendation_status"] == "marginal_observe"


def test_positive_edge_with_minimum_bet_within_risk_limit_recommends_units() -> None:
    result = suggest_bankroll_exposure(
        bankroll=1000,
        minimum_bet=10,
        estimated_player_edge=0.05,
    )

    assert result["suggested_units"] == 2
    assert result["suggested_amount"] == 20
    assert result["minimum_bet_exceeds_risk_cap"] is False
    assert result["risk_if_minimum_bet"] is not None
    assert result["risk_if_minimum_bet"] <= 0.05


def test_high_positive_edge_is_capped_at_five_percent() -> None:
    result = suggest_bankroll_exposure(
        bankroll=1000,
        minimum_bet=10,
        estimated_player_edge=1.0,
    )

    assert result["should_enter"] is True
    assert result["suggested_units"] == 5
    assert result["suggested_amount"] == 50
    assert result["suggested_amount"] <= 1000 * MAX_SINGLE_ROUND_EXPOSURE
    assert result["estimated_risk_of_ruin"] <= RISK_OF_RUIN_LIMIT
    assert result["recommendation_status"] == "favorable_risk_capped"


def test_suggested_amount_is_units_times_minimum_bet() -> None:
    result = suggest_bankroll_exposure(
        bankroll=5000,
        minimum_bet=7.5,
        estimated_player_edge=0.2,
    )

    assert result["suggested_amount"] == pytest.approx(
        result["suggested_units"] * 7.5
    )
    assert result["suggested_amount"] <= (
        5000 * MAX_SINGLE_ROUND_EXPOSURE
    )


def test_subnormal_minimum_bet_does_not_overflow_unit_calculation() -> None:
    result = suggest_bankroll_exposure(
        bankroll=1.0,
        minimum_bet=5e-324,
        estimated_player_edge=1.0,
    )

    assert result["suggested_units"] > 0
    assert math.isfinite(result["suggested_amount"])
    assert result["suggested_amount"] <= MAX_SINGLE_ROUND_EXPOSURE


def test_bankroll_exposure_percent_is_amount_over_bankroll() -> None:
    result = suggest_bankroll_exposure(
        bankroll=1000,
        minimum_bet=10,
        estimated_player_edge=0.05,
    )

    assert result["bankroll_exposure_percent"] == pytest.approx(20 / 1000)
    assert result["selected_bet_fraction"] == pytest.approx(20 / 1000)


def test_risk_estimate_matches_documented_formula() -> None:
    risk = estimate_risk_of_ruin(
        bankroll=1000,
        bet_amount=20,
        estimated_player_edge=0.05,
    )

    expected = math.exp((-2 * 0.05 * 1000) / (1.3 * 20))
    assert risk == pytest.approx(expected)


def test_zero_exposure_has_zero_estimated_risk() -> None:
    assert estimate_risk_of_ruin(1000, 0, 0.05) == 0


@pytest.mark.parametrize(
    ("bankroll", "edge", "expected"),
    [(0, 0.05, 1.0), (1000, 0.0, 1.0), (1000, -0.01, 1.0)],
)
def test_positive_exposure_without_positive_drift_has_maximum_risk(
    bankroll: float,
    edge: float,
    expected: float,
) -> None:
    assert estimate_risk_of_ruin(bankroll, 10, edge) == expected


def test_max_bet_for_five_percent_risk_matches_formula() -> None:
    max_bet = calculate_max_bet_for_risk_limit(
        bankroll=1000,
        estimated_player_edge=0.05,
    )

    expected = (2 * 0.05 * 1000) / (1.3 * math.log(20))
    assert max_bet == pytest.approx(expected)


def test_minimum_bankroll_for_bet_at_risk_limit_matches_formula() -> None:
    bankroll_required = calculate_minimum_bankroll_for_bet_at_risk_limit(
        bet_amount=5,
        estimated_player_edge=0.0196,
    )

    expected = (1.3 * 5 * math.log(20)) / (2 * 0.0196)
    assert bankroll_required == pytest.approx(expected)


@pytest.mark.parametrize(
    ("bet_amount", "edge", "expected"),
    [(0, 0.05, None), (-1, 0.05, None), (10, 0.0, None), (10, -0.01, None)],
)
def test_minimum_bankroll_helper_returns_none_for_non_applicable_inputs(
    bet_amount: float,
    edge: float,
    expected: None,
) -> None:
    assert (
        calculate_minimum_bankroll_for_bet_at_risk_limit(
            bet_amount=bet_amount,
            estimated_player_edge=edge,
        )
        is expected
    )


@pytest.mark.parametrize("edge", [0.005, 0.02, 0.05, 0.06, 0.2, 1.0])
def test_every_positive_exposure_respects_risk_limit(edge: float) -> None:
    result = suggest_bankroll_exposure(1000, 10, edge)

    if result["suggested_amount"] > 0:
        assert result["estimated_risk_of_ruin"] <= result["risk_of_ruin_limit"]


@pytest.mark.parametrize("risk_limit", [0, 1, -0.1, 1.1])
def test_invalid_risk_limit_raises_clear_error(risk_limit: float) -> None:
    with pytest.raises(
        ValueError,
        match="risk_of_ruin_limit must be greater than 0 and less than 1",
    ):
        calculate_max_bet_for_risk_limit(
            bankroll=1000,
            estimated_player_edge=0.05,
            risk_of_ruin_limit=risk_limit,
        )

    with pytest.raises(ValueError, match="risk_of_ruin_limit"):
        suggest_bankroll_exposure(
            bankroll=1000,
            minimum_bet=10,
            estimated_player_edge=0.05,
            risk_of_ruin_limit=risk_limit,
        )

    with pytest.raises(ValueError, match="risk_of_ruin_limit"):
        calculate_minimum_bankroll_for_bet_at_risk_limit(
            bet_amount=10,
            estimated_player_edge=0.05,
            risk_of_ruin_limit=risk_limit,
        )


@pytest.mark.parametrize("variance", [0, -1])
def test_invalid_variance_raises_clear_error(variance: float) -> None:
    with pytest.raises(
        ValueError,
        match="variance_per_unit must be greater than zero",
    ):
        estimate_risk_of_ruin(1000, 10, 0.05, variance)

    with pytest.raises(ValueError, match="variance_per_unit"):
        calculate_max_bet_for_risk_limit(1000, 0.05, 0.05, variance)

    with pytest.raises(ValueError, match="variance_per_unit"):
        suggest_bankroll_exposure(
            1000,
            10,
            0.05,
            variance_per_unit=variance,
        )

    with pytest.raises(ValueError, match="variance_per_unit"):
        calculate_minimum_bankroll_for_bet_at_risk_limit(
            bet_amount=10,
            estimated_player_edge=0.05,
            variance_per_unit=variance,
        )


@pytest.mark.parametrize("edge", [math.nan, math.inf, -math.inf, "0.05", True])
def test_invalid_estimated_edge_raises_clear_error(edge: object) -> None:
    with pytest.raises(
        ValueError,
        match="estimated_player_edge must be a finite number",
    ):
        suggest_bankroll_exposure(
            bankroll=1000,
            minimum_bet=10,
            estimated_player_edge=edge,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("cards_remaining", [-1, 1.5, True])
def test_invalid_cards_remaining_raises_clear_error(
    cards_remaining: object,
) -> None:
    with pytest.raises(
        ValueError,
        match="cards_remaining must be a non-negative integer",
    ):
        suggest_bankroll_exposure(
            bankroll=1000,
            minimum_bet=10,
            estimated_player_edge=0.05,
            cards_remaining=cards_remaining,  # type: ignore[arg-type]
        )


def test_cards_remaining_zero_is_accepted() -> None:
    result = suggest_bankroll_exposure(
        bankroll=1000,
        minimum_bet=10,
        estimated_player_edge=0.05,
        cards_remaining=0,
    )

    assert result["suggested_units"] == 2


@pytest.mark.parametrize(
    ("bankroll", "minimum_bet", "edge"),
    [
        (1000, 10, -0.005),
        (1000, 10, 0.05),
        (1000, 10, 1.0),
        (5, 10, 0.05),
    ],
)
def test_recommendation_never_contains_invalid_numeric_outputs(
    bankroll: float,
    minimum_bet: float,
    edge: float,
) -> None:
    result = suggest_bankroll_exposure(bankroll, minimum_bet, edge)

    for field in (
        "suggested_units",
        "suggested_amount",
        "bankroll_exposure_percent",
        "max_protected_amount",
        "estimated_player_edge",
        "estimated_risk_of_ruin",
        "risk_of_ruin_limit",
        "variance_per_unit",
        "max_bet_by_risk",
        "max_single_round_exposure",
        "max_bet_by_exposure",
        "selected_bet_fraction",
        "kelly_fraction",
        "risk_limited_fraction",
    ):
        value = result[field]
        assert isinstance(value, (int, float))
        assert math.isfinite(value)
        assert value >= 0 or field == "estimated_player_edge"

    for optional_field in (
        "risk_if_minimum_bet",
        "minimum_bankroll_required_for_minimum_bet",
    ):
        optional_value = result[optional_field]
        if optional_value is not None:
            assert isinstance(optional_value, (int, float))
            assert math.isfinite(optional_value)
            assert optional_value >= 0

    assert isinstance(result["minimum_bet_exceeds_risk_cap"], bool)


def test_system_id_is_only_echoed_as_metadata() -> None:
    result = suggest_bankroll_exposure(
        bankroll=1000,
        minimum_bet=10,
        estimated_player_edge=0.06,
        system_id="hi_lo",
    )

    assert result["system_id"] == "hi_lo"


def test_policy_info_returns_risk_capped_identity_and_constants() -> None:
    info = get_bankroll_policy_info()

    assert info["policy_id"] == POLICY_ID == "risk_capped_growth"
    assert info["variance_per_unit"] == VARIANCE_PER_UNIT
    assert info["risk_of_ruin_limit"] == RISK_OF_RUIN_LIMIT
    assert (
        info["max_single_round_exposure"]
        == MAX_SINGLE_ROUND_EXPOSURE
    )
    assert info["max_bankroll_exposure"] == MAX_BANKROLL_EXPOSURE
    assert info["risk_model"] == RISK_MODEL
