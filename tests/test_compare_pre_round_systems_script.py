from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from types import ModuleType

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "compare_pre_round_systems.py"
)


@pytest.fixture(scope="module")
def comparator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "compare_pre_round_systems",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _system(analysis: dict[str, object], system_id: str) -> dict[str, object]:
    systems = analysis["systems"]
    assert isinstance(systems, list)
    return next(system for system in systems if system["system_id"] == system_id)


def _numeric_values(value: object):
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield float(value)
        return
    if isinstance(value, dict):
        for nested in value.values():
            yield from _numeric_values(nested)
        return
    if isinstance(value, (list, tuple)):
        for nested in value:
            yield from _numeric_values(nested)


def test_script_imports_and_defines_all_required_scenarios(
    comparator: ModuleType,
) -> None:
    scenario_ids = {
        scenario.scenario_id
        for scenario in comparator.SCENARIOS
    }

    assert scenario_ids == {
        "neutral_shoe",
        "low_cards_removed",
        "high_cards_removed",
        "fours_and_fives",
        "relative_ace_surplus",
        "relative_ace_shortage",
        "extreme_favorable_controlled",
        "extreme_favorable_six_to_five",
    }


def test_every_scenario_returns_three_finite_system_results(
    comparator: ModuleType,
) -> None:
    results = comparator.run_scenarios()

    assert len(results) == 8
    for scenario, analysis in results:
        assert scenario.seen_cards is not None
        assert [
            system["system_id"]
            for system in analysis["systems"]
        ] == ["hi_lo", "hi_opt_ii", "wong_halves"]
        assert all(
            math.isfinite(value)
            for value in _numeric_values(analysis)
        )


def test_neutral_and_high_card_scenarios_recommend_observe(
    comparator: ModuleType,
) -> None:
    analyses = {
        scenario.scenario_id: analysis
        for scenario, analysis in comparator.run_scenarios()
    }

    for scenario_id in ("neutral_shoe", "high_cards_removed"):
        for system in analyses[scenario_id]["systems"]:
            assert system["should_enter"] is False
            assert system["recommendation_status"] == "observe"


def test_hi_opt_ii_reacts_more_to_fours_and_fives_than_hi_lo(
    comparator: ModuleType,
) -> None:
    scenario = next(
        scenario
        for scenario in comparator.SCENARIOS
        if scenario.scenario_id == "fours_and_fives"
    )
    analysis = comparator.run_scenario(scenario)
    hi_lo = _system(analysis, "hi_lo")
    hi_opt_ii = _system(analysis, "hi_opt_ii")

    assert hi_opt_ii["playing_running_count"] > hi_lo["running_count"]


def test_ace_scenarios_have_expected_excess_sign(
    comparator: ModuleType,
) -> None:
    analyses = {
        scenario.scenario_id: analysis
        for scenario, analysis in comparator.run_scenarios()
    }
    surplus = _system(analyses["relative_ace_surplus"], "hi_opt_ii")
    shortage = _system(analyses["relative_ace_shortage"], "hi_opt_ii")

    assert surplus["ace_side_count"]["excess_aces"] > 0
    assert shortage["ace_side_count"]["excess_aces"] < 0


def test_extreme_scenario_respects_bankroll_cap(
    comparator: ModuleType,
) -> None:
    scenario = next(
        scenario
        for scenario in comparator.SCENARIOS
        if scenario.scenario_id == "extreme_favorable_controlled"
    )
    analysis = comparator.run_scenario(scenario)

    assert any(system["suggested_units"] > 0 for system in analysis["systems"])
    for system in analysis["systems"]:
        assert system["suggested_amount"] <= (
            comparator.BANKROLL * 0.05
        )
        if system["suggested_amount"] > 0:
            assert (
                system["estimated_risk_of_ruin"]
                <= system["risk_of_ruin_limit"]
            )


def test_six_to_five_worsens_same_shoe_for_every_system(
    comparator: ModuleType,
) -> None:
    analyses = {
        scenario.scenario_id: analysis
        for scenario, analysis in comparator.run_scenarios()
    }
    standard = analyses["extreme_favorable_controlled"]
    six_to_five = analyses["extreme_favorable_six_to_five"]

    for system_id in ("hi_lo", "hi_opt_ii", "wong_halves"):
        standard_system = _system(standard, system_id)
        six_to_five_system = _system(six_to_five, system_id)
        assert (
            six_to_five_system["estimated_player_edge"]
            < standard_system["estimated_player_edge"]
        )


def test_wong_halves_preserves_integer_scale(
    comparator: ModuleType,
) -> None:
    scenario = next(
        scenario
        for scenario in comparator.SCENARIOS
        if scenario.scenario_id == "low_cards_removed"
    )
    wong_halves = _system(
        comparator.run_scenario(scenario),
        "wong_halves",
    )

    assert wong_halves["scale"] == 2
    assert isinstance(wong_halves["scaled_running_count"], int)
    assert (
        wong_halves["running_count"]
        == wong_halves["scaled_running_count"] / 2
    )
