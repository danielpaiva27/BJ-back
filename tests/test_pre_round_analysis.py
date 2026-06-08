import math

import pytest
import blackjack_risk_engine.engine_core.pre_round.analysis as pre_round_analysis_module

from blackjack_risk_engine.engine_core.pre_round import (
    ACE_ADJUSTMENT_FACTOR,
    MAX_BANKROLL_EXPOSURE,
    RISK_OF_RUIN_LIMIT,
    VARIANCE_PER_UNIT,
    analyze_pre_round,
)


def _system_result(
    analysis: dict[str, object],
    system_id: str,
) -> dict[str, object]:
    systems = analysis["systems"]
    assert isinstance(systems, list)
    return next(
        system
        for system in systems
        if isinstance(system, dict) and system["system_id"] == system_id
    )


def _assert_all_numbers_are_finite(value: object) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        assert math.isfinite(value)
        return
    if isinstance(value, dict):
        for nested_value in value.values():
            _assert_all_numbers_are_finite(nested_value)
        return
    if isinstance(value, list):
        for nested_value in value:
            _assert_all_numbers_are_finite(nested_value)


def test_analyze_pre_round_returns_all_systems_by_default() -> None:
    result = analyze_pre_round(
        number_of_decks=6,
        seen_cards=[],
        bankroll=1000,
        minimum_bet=10,
    )

    assert [
        system["system_id"] for system in result["systems"]
    ] == ["hi_lo", "hi_opt_ii", "wong_halves"]
    assert result["cards_seen"] == 0
    assert result["cards_remaining"] == 312
    assert result["decks_remaining"] == 6
    assert result["policy"]["policy_id"] == "risk_capped_growth"


def test_analyze_pre_round_can_filter_systems() -> None:
    result = analyze_pre_round(
        number_of_decks=6,
        seen_cards=[],
        bankroll=1000,
        minimum_bet=10,
        systems=["hi_lo"],
    )

    assert [system["system_id"] for system in result["systems"]] == ["hi_lo"]


def test_requested_system_order_is_preserved() -> None:
    result = analyze_pre_round(
        number_of_decks=6,
        seen_cards=[],
        bankroll=1000,
        minimum_bet=10,
        systems=["wong_halves", "hi_opt_ii"],
    )

    assert [
        system["system_id"] for system in result["systems"]
    ] == ["wong_halves", "hi_opt_ii"]


def test_empty_system_selection_raises_clear_error() -> None:
    with pytest.raises(
        ValueError,
        match=r"At least one counting system must be provided\.",
    ):
        analyze_pre_round(6, [], 1000, 10, systems=[])


def test_invalid_system_raises_clear_error() -> None:
    with pytest.raises(ValueError, match=r"unknown count system 'banana_count'"):
        analyze_pre_round(6, [], 1000, 10, systems=["banana_count"])


def test_duplicate_system_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="provided more than once"):
        analyze_pre_round(6, [], 1000, 10, systems=["hi_lo", "hi_lo"])


def test_hi_lo_uses_true_count_as_betting_true_count() -> None:
    result = analyze_pre_round(
        number_of_decks=6,
        seen_cards=["2", "3", "10", "A"],
        bankroll=1000,
        minimum_bet=10,
        systems=["hi_lo"],
    )
    hi_lo = _system_result(result, "hi_lo")

    assert hi_lo["running_count"] == 0
    assert hi_lo["true_count"] == 0
    assert hi_lo["betting_true_count"] == 0


def test_hi_opt_ii_exposes_playing_and_betting_counts() -> None:
    result = analyze_pre_round(
        number_of_decks=6,
        seen_cards=["4", "5", "10", "A"],
        bankroll=1000,
        minimum_bet=10,
        systems=["hi_opt_ii"],
    )
    hi_opt = _system_result(result, "hi_opt_ii")

    assert hi_opt["running_count"] == 2
    assert hi_opt["playing_running_count"] == 2
    assert hi_opt["playing_true_count"] == hi_opt["true_count"]
    assert hi_opt["ace_adjustment_factor"] == ACE_ADJUSTMENT_FACTOR
    assert isinstance(hi_opt["ace_side_count"], dict)
    assert isinstance(hi_opt["betting_true_count"], float)


def test_hi_opt_ii_has_excess_aces_when_no_aces_have_been_seen() -> None:
    seen_cards = ["2", "3", "4", "5"]
    result = analyze_pre_round(
        number_of_decks=1,
        seen_cards=seen_cards,
        bankroll=1000,
        minimum_bet=10,
        systems=["hi_opt_ii"],
    )
    hi_opt = _system_result(result, "hi_opt_ii")
    ace_side_count = hi_opt["ace_side_count"]

    assert ace_side_count["total_aces"] == 4
    assert ace_side_count["seen_aces"] == 0
    assert ace_side_count["aces_remaining"] == 4
    assert ace_side_count["expected_aces_remaining"] == pytest.approx(48 / 52 * 4)
    assert ace_side_count["excess_aces"] > 0


def test_hi_opt_ii_has_ace_deficit_when_aces_have_been_seen() -> None:
    result = analyze_pre_round(
        number_of_decks=1,
        seen_cards=["A"] * 4,
        bankroll=1000,
        minimum_bet=10,
        systems=["hi_opt_ii"],
    )
    hi_opt = _system_result(result, "hi_opt_ii")
    ace_side_count = hi_opt["ace_side_count"]

    assert ace_side_count["seen_aces"] == 4
    assert ace_side_count["aces_remaining"] == 0
    assert ace_side_count["excess_aces"] < 0


def test_hi_opt_ii_betting_count_uses_ace_adjustment() -> None:
    result = analyze_pre_round(
        number_of_decks=1,
        seen_cards=["2", "3", "4", "5"],
        bankroll=1000,
        minimum_bet=10,
        systems=["hi_opt_ii"],
    )
    hi_opt = _system_result(result, "hi_opt_ii")
    ace_side_count = hi_opt["ace_side_count"]
    expected_betting_running_count = (
        hi_opt["playing_running_count"]
        + ace_side_count["excess_aces"] * ACE_ADJUSTMENT_FACTOR
    )

    assert hi_opt["betting_running_count"] == pytest.approx(
        expected_betting_running_count
    )
    assert hi_opt["betting_true_count"] == pytest.approx(
        expected_betting_running_count / result["decks_remaining"]
    )


def test_wong_halves_preserves_scaled_running_count() -> None:
    result = analyze_pre_round(
        number_of_decks=6,
        seen_cards=["2", "5", "9", "10", "A"],
        bankroll=1000,
        minimum_bet=10,
        systems=["wong_halves"],
    )
    wong_halves = _system_result(result, "wong_halves")

    assert wong_halves["scaled_running_count"] == -1
    assert wong_halves["running_count"] == -0.5
    assert wong_halves["betting_true_count"] == wong_halves["true_count"]


def test_every_system_includes_edge_and_bankroll_recommendation() -> None:
    result = analyze_pre_round(6, [], 1000, 10)

    expected_fields = {
        "estimated_player_edge",
        "should_enter",
        "suggested_units",
        "suggested_amount",
        "bankroll_exposure_percent",
        "estimated_risk_of_ruin",
        "risk_of_ruin_limit",
        "risk_model",
        "max_bet_by_risk",
        "max_bet_by_exposure",
        "selected_bet_fraction",
        "kelly_fraction",
        "risk_limited_fraction",
        "risk_if_minimum_bet",
        "minimum_bankroll_required_for_minimum_bet",
        "minimum_bet_exceeds_risk_cap",
        "recommendation_status",
        "recommendation_text",
    }
    for system in result["systems"]:
        assert expected_fields <= system.keys()


def test_neutral_shoe_recommends_observing() -> None:
    result = analyze_pre_round(6, [], 1000, 10)

    for system in result["systems"]:
        assert system["estimated_player_edge"] < 0
        assert system["suggested_units"] == 0
        assert system["recommendation_status"] == "observe"


def test_insufficient_bankroll_is_reported_for_every_system() -> None:
    result = analyze_pre_round(6, [], bankroll=5, minimum_bet=10)

    for system in result["systems"]:
        assert system["should_enter"] is False
        assert system["suggested_units"] == 0
        assert system["recommendation_status"] == "insufficient_bankroll"


def test_positive_edge_minimum_bet_exceeds_risk_cap_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pre_round_analysis_module,
        "estimate_player_edge",
        lambda **_: 0.0196,
    )

    result = analyze_pre_round(6, [], bankroll=200, minimum_bet=5)
    expected_minimum_bankroll_required = (
        VARIANCE_PER_UNIT * 5 * math.log(1 / RISK_OF_RUIN_LIMIT)
    ) / (2 * 0.0196)

    for system in result["systems"]:
        assert system["should_enter"] is False
        assert system["suggested_units"] == 0
        assert system["recommendation_status"] == (
            "positive_edge_minimum_bet_exceeds_risk_cap"
        )
        assert system["minimum_bet_exceeds_risk_cap"] is True
        assert system["risk_if_minimum_bet"] > 0.05
        assert system[
            "minimum_bankroll_required_for_minimum_bet"
        ] == pytest.approx(expected_minimum_bankroll_required)


def test_favorable_shoe_can_produce_protected_exposure() -> None:
    low_cards = (
        ["2"] * 4
        + ["3"] * 4
        + ["4"] * 4
        + ["5"] * 4
        + ["6"] * 4
    )
    result = analyze_pre_round(
        number_of_decks=1,
        seen_cards=low_cards,
        bankroll=1000,
        minimum_bet=10,
    )
    positive_systems = [
        system
        for system in result["systems"]
        if system["estimated_player_edge"] > 0
    ]

    assert positive_systems
    assert any(system["suggested_units"] > 0 for system in positive_systems)
    for system in positive_systems:
        assert system["suggested_amount"] <= 1000 * MAX_BANKROLL_EXPOSURE
        if system["suggested_amount"] > 0:
            assert system["estimated_risk_of_ruin"] <= RISK_OF_RUIN_LIMIT


def test_full_shoe_returns_safe_zero_true_counts() -> None:
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
    result = analyze_pre_round(1, full_shoe, 1000, 10)

    assert result["cards_remaining"] == 0
    assert result["decks_remaining"] == 0
    for system in result["systems"]:
        assert system["true_count"] == 0
        assert system["betting_true_count"] == 0
    _assert_all_numbers_are_finite(result)


def test_all_numeric_result_fields_are_finite() -> None:
    result = analyze_pre_round(
        6,
        ["2", "3", "4", "5", "6", "10", "A"],
        1000,
        10,
    )

    _assert_all_numbers_are_finite(result)


def test_most_favorable_system_is_selected_by_highest_edge() -> None:
    result = analyze_pre_round(
        1,
        ["2", "3", "4", "5", "6"],
        1000,
        10,
    )
    expected = max(
        result["systems"],
        key=lambda system: system["estimated_player_edge"],
    )

    assert result["most_favorable_estimate_system_id"] == expected["system_id"]


def test_tied_estimates_select_the_first_requested_system() -> None:
    result = analyze_pre_round(
        6,
        [],
        1000,
        10,
        systems=["wong_halves", "hi_lo"],
    )

    assert result["most_favorable_estimate_system_id"] == "wong_halves"


def test_result_contains_no_risk_profile_fields() -> None:
    result = analyze_pre_round(6, [], 1000, 10)
    forbidden_keys = {
        "risk_profile",
        "conservative",
        "moderate",
        "aggressive",
        "conservador",
        "moderado",
        "agressivo",
    }

    def assert_no_forbidden_keys(value: object) -> None:
        if isinstance(value, dict):
            assert forbidden_keys.isdisjoint(value)
            for nested_value in value.values():
                assert_no_forbidden_keys(nested_value)
        elif isinstance(value, list):
            for nested_value in value:
                assert_no_forbidden_keys(nested_value)

    assert_no_forbidden_keys(result)


def test_too_many_aces_raises_clear_error() -> None:
    with pytest.raises(ValueError, match=r"5 copies of A"):
        analyze_pre_round(1, ["A"] * 5, 1000, 10)


def test_too_many_tens_raises_clear_error() -> None:
    with pytest.raises(ValueError, match=r"17 copies of 10"):
        analyze_pre_round(1, ["10"] * 17, 1000, 10)


def test_invalid_card_raises_clear_error() -> None:
    with pytest.raises(ValueError, match=r"invalid blackjack card 'X'"):
        analyze_pre_round(6, ["X"], 1000, 10)


def test_six_to_five_rules_worsen_estimated_edge() -> None:
    three_to_two = analyze_pre_round(
        6,
        [],
        1000,
        10,
        rules={"blackjack_payout": "3:2"},
        systems=["hi_lo"],
    )
    six_to_five = analyze_pre_round(
        6,
        [],
        1000,
        10,
        rules={"blackjack_payout": "6:5"},
        systems=["hi_lo"],
    )

    assert (
        _system_result(six_to_five, "hi_lo")["estimated_player_edge"]
        < _system_result(three_to_two, "hi_lo")["estimated_player_edge"]
    )


@pytest.mark.parametrize("field", ["bankroll", "minimum_bet"])
@pytest.mark.parametrize("invalid_value", [math.nan, math.inf, -math.inf, True])
def test_non_finite_or_non_numeric_financial_input_raises_clear_error(
    field: str,
    invalid_value: object,
) -> None:
    arguments = {
        "number_of_decks": 6,
        "seen_cards": [],
        "bankroll": 1000,
        "minimum_bet": 10,
    }
    arguments[field] = invalid_value

    with pytest.raises(ValueError, match=rf"{field} must be a finite number"):
        analyze_pre_round(**arguments)


def test_invalid_bankroll_status_is_reused_from_policy() -> None:
    result = analyze_pre_round(6, [], bankroll=0, minimum_bet=10)

    for system in result["systems"]:
        assert system["recommendation_status"] == "invalid_bankroll"


def test_invalid_minimum_bet_status_is_reused_from_policy() -> None:
    result = analyze_pre_round(6, [], bankroll=1000, minimum_bet=0)

    for system in result["systems"]:
        assert system["recommendation_status"] == "invalid_minimum_bet"


def test_extreme_numeric_inputs_raise_clear_errors() -> None:
    with pytest.raises(ValueError, match="bankroll must be a finite number"):
        analyze_pre_round(6, [], bankroll=10**1000, minimum_bet=10)

    with pytest.raises(ValueError, match="number_of_decks is too large"):
        analyze_pre_round(10**1000, [], bankroll=1000, minimum_bet=10)
