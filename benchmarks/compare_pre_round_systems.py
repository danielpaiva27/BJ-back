from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from blackjack_risk_engine.engine_core.pre_round import analyze_pre_round


Rules: TypeAlias = dict[str, object]
Analysis: TypeAlias = dict[str, object]

NUMBER_OF_DECKS = 6
BANKROLL = 1000.0
MINIMUM_BET = 10.0
STANDARD_RULES: Rules = {
    "blackjack_payout": "3:2",
    "dealer_hits_soft_17": False,
    "double_after_split": True,
    "surrender_allowed": False,
    "dealer_peek": True,
}

EXTREME_LOW_CARDS = tuple(
    rank
    for rank in ("2", "3", "4", "5", "6")
    for _ in range(20)
)


@dataclass(frozen=True, slots=True)
class PreRoundScenario:
    scenario_id: str
    label: str
    seen_cards: tuple[str, ...]
    rules: Rules


SCENARIOS: tuple[PreRoundScenario, ...] = (
    PreRoundScenario(
        scenario_id="neutral_shoe",
        label="Neutral shoe",
        seen_cards=(),
        rules=STANDARD_RULES,
    ),
    PreRoundScenario(
        scenario_id="low_cards_removed",
        label="Many low cards removed",
        seen_cards=(
            "2", "3", "4", "5", "6",
            "2", "3", "4", "5", "6",
            "2", "3", "4", "5", "6",
        ),
        rules=STANDARD_RULES,
    ),
    PreRoundScenario(
        scenario_id="high_cards_removed",
        label="Many high cards removed",
        seen_cards=("10", "10", "10", "10", "A", "A", "10", "A", "10", "10"),
        rules=STANDARD_RULES,
    ),
    PreRoundScenario(
        scenario_id="fours_and_fives",
        label="Many fours and fives removed",
        seen_cards=("4", "5", "4", "5", "4", "5", "10", "A"),
        rules=STANDARD_RULES,
    ),
    PreRoundScenario(
        scenario_id="relative_ace_surplus",
        label="Relative surplus of remaining aces",
        seen_cards=(
            "2", "3", "4", "5", "6", "7", "8", "9", "10",
            "2", "3", "4", "5", "6", "7", "8", "9", "10",
        ),
        rules=STANDARD_RULES,
    ),
    PreRoundScenario(
        scenario_id="relative_ace_shortage",
        label="Relative shortage of remaining aces",
        seen_cards=("A", "A", "A", "A", "A", "A", "2", "3", "4", "5"),
        rules=STANDARD_RULES,
    ),
    PreRoundScenario(
        scenario_id="extreme_favorable_controlled",
        label="Extreme favorable shoe with bankroll cap",
        seen_cards=EXTREME_LOW_CARDS,
        rules=STANDARD_RULES,
    ),
    PreRoundScenario(
        scenario_id="extreme_favorable_six_to_five",
        label="Same extreme shoe with blackjack 6:5",
        seen_cards=EXTREME_LOW_CARDS,
        rules={**STANDARD_RULES, "blackjack_payout": "6:5"},
    ),
)


def run_scenario(scenario: PreRoundScenario) -> Analysis:
    return analyze_pre_round(
        number_of_decks=NUMBER_OF_DECKS,
        seen_cards=scenario.seen_cards,
        bankroll=BANKROLL,
        minimum_bet=MINIMUM_BET,
        rules=scenario.rules,
    )


def run_scenarios() -> list[tuple[PreRoundScenario, Analysis]]:
    return [(scenario, run_scenario(scenario)) for scenario in SCENARIOS]


def iter_numeric_values(value: object):
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield float(value)
        return
    if isinstance(value, dict):
        for nested in value.values():
            yield from iter_numeric_values(nested)
        return
    if isinstance(value, (list, tuple)):
        for nested in value:
            yield from iter_numeric_values(nested)


def assert_finite_analysis(analysis: Analysis) -> None:
    for value in iter_numeric_values(analysis):
        if not math.isfinite(value):
            raise RuntimeError("pre-round analysis produced a non-finite number")


def _signed_number(value: object, digits: int = 2) -> str:
    return f"{float(value):+.{digits}f}"


def _percent(value: object) -> str:
    return f"{float(value) * 100:+.2f}%"


def _print_system(system: dict[str, object]) -> None:
    print(f"\n{system['label']}:")
    print(f"  RC: {_signed_number(system['running_count'])}")
    print(f"  TC: {_signed_number(system['true_count'])}")
    print(f"  Betting TC: {_signed_number(system['betting_true_count'])}")
    print(f"  Edge: {_percent(system['estimated_player_edge'])}")
    print(
        "  Suggestion: "
        f"{system['suggested_units']} units / "
        f"{float(system['suggested_amount']):.2f}"
    )
    print(f"  Status: {system['recommendation_status']}")
    print(f"  Should enter: {system['should_enter']}")
    if float(system["suggested_amount"]) > 0:
        print(
            "  Estimated ruin risk: "
            f"{_percent(system['estimated_risk_of_ruin'])} / "
            f"limit {_percent(system['risk_of_ruin_limit'])}"
        )
    else:
        print("  Estimated ruin risk: no suggested exposure")

    if system["system_id"] == "hi_opt_ii":
        ace_side_count = system["ace_side_count"]
        if not isinstance(ace_side_count, dict):
            raise RuntimeError("Hi-Opt II result is missing ace_side_count")
        print(
            "  Playing TC: "
            f"{_signed_number(system['playing_true_count'])}"
        )
        print(
            "  Ace excess: "
            f"{_signed_number(ace_side_count['excess_aces'])}"
        )
        print(
            "  Betting RC: "
            f"{_signed_number(system['betting_running_count'])}"
        )

    if system["system_id"] == "wong_halves":
        print(f"  Scaled RC: {system['scaled_running_count']:+d}")
        print(f"  Scale: {system['scale']}")
        print(
            "  Fractional RC: "
            f"{_signed_number(system['running_count'])}"
        )


def print_report(results: list[tuple[PreRoundScenario, Analysis]]) -> None:
    for scenario, analysis in results:
        assert_finite_analysis(analysis)
        print(f"\n=== Scenario: {scenario.label} ===")
        print(f"Scenario id: {scenario.scenario_id}")
        print(f"Cards seen: {analysis['cards_seen']}")
        print(f"Cards remaining: {analysis['cards_remaining']}")
        print(f"Decks remaining: {float(analysis['decks_remaining']):.4f}")

        systems = analysis["systems"]
        if not isinstance(systems, list):
            raise RuntimeError("analysis systems must be a list")
        for system in systems:
            if not isinstance(system, dict):
                raise RuntimeError("system result must be a dictionary")
            _print_system(system)

        print(
            "\nMost favorable estimate: "
            f"{analysis['most_favorable_estimate_system_id']}"
        )

    print("\nPre-round system comparison completed successfully.")
    print(f"Scenarios executed: {len(results)}")


def main() -> None:
    print_report(run_scenarios())


if __name__ == "__main__":
    main()
