from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Mapping, Sequence


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = PROJECT_ROOT / "benchmarks"
sys.path.insert(0, str(BENCHMARK_DIR))

from compare_machine_ev_vs_counting_systems import (
    BenchmarkResult,
    ComparisonScenario,
    SCENARIOS,
    run_scenario,
)


AUDIT_SCENARIO_IDS = (
    "neutral_6_decks",
    "low_cards_removed",
    "high_cards_removed",
    "late_shoe_composition",
    "blackjack_6_to_5",
    "neutral_h17",
    "surrender_allowed",
    "small_bankroll_high_minimum",
)
SMOKE_SCENARIO_IDS = (
    "late_shoe_composition",
)
NEUTRAL_STANDARD_SCENARIO_IDS = {"neutral_6_decks"}
NEUTRAL_EDGE_MIN = -0.02
NEUTRAL_EDGE_MAX = 0.001


def audit_scenario(result: BenchmarkResult) -> dict[str, object]:
    machine = result.get("machine_ev")
    if not isinstance(machine, Mapping):
        raise RuntimeError("benchmark result is missing machine_ev")

    edge = _finite_float(
        machine.get("estimated_next_hand_edge"),
        "estimated_next_hand_edge",
    )
    duration_ms = _finite_float(machine.get("duration_ms"), "duration_ms")
    states_evaluated = machine.get("states_evaluated")
    risk = machine.get("risk_if_minimum_bet")
    required_bankroll = machine.get(
        "minimum_bankroll_required_for_minimum_bet"
    )

    checks = {
        "edge_finite": math.isfinite(edge),
        "edge_plausible": -1 <= edge <= 1,
        "duration_valid": duration_ms >= 0,
        "states_evaluated": (
            isinstance(states_evaluated, int)
            and not isinstance(states_evaluated, bool)
            and states_evaluated > 0
        ),
        "risk_valid": (
            risk is None
            or (
                isinstance(risk, (int, float))
                and not isinstance(risk, bool)
                and math.isfinite(float(risk))
                and 0 <= float(risk) <= 1
            )
        ),
        "required_bankroll_valid": (
            required_bankroll is None
            or (
                isinstance(required_bankroll, (int, float))
                and not isinstance(required_bankroll, bool)
                and math.isfinite(float(required_bankroll))
                and float(required_bankroll) > 0
            )
        ),
        "separate_model": (
            machine.get("model_id") == "machine_ev"
            and machine.get("is_human_replicable") is False
            and "counting_systems" in result
        ),
    }
    if result.get("scenario_id") in NEUTRAL_STANDARD_SCENARIO_IDS:
        checks["neutral_standard_edge_sane"] = (
            NEUTRAL_EDGE_MIN <= edge <= NEUTRAL_EDGE_MAX
        )
    return {
        "scenario_id": result["scenario_id"],
        "edge": edge,
        "risk_if_minimum_bet": risk,
        "minimum_bankroll_required_for_minimum_bet": required_bankroll,
        "recommendation_status": machine.get("recommendation_status"),
        "checks": checks,
        "passed": all(checks.values()),
    }


def run_accuracy_audit(
    scenarios: Sequence[ComparisonScenario],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    results = [run_scenario(scenario) for scenario in scenarios]
    scenario_audits = [audit_scenario(result) for result in results]
    by_id = {
        str(result["scenario_id"]): result
        for result in results
    }
    direction_audits = _direction_audits(by_id)
    return scenario_audits, direction_audits


def print_audit_report(
    scenario_audits: Sequence[dict[str, object]],
    direction_audits: Sequence[dict[str, object]],
) -> None:
    print("Machine EV accuracy audit")
    print(
        "scenario | edge | risk_min | bankroll_required | status | checks"
    )
    for audit in scenario_audits:
        print(
            f"{audit['scenario_id']} | "
            f"{float(audit['edge']) * 100:+.2f}% | "
            f"{_optional_percent(audit['risk_if_minimum_bet'])} | "
            f"{_optional_number(audit['minimum_bankroll_required_for_minimum_bet'])} | "
            f"{audit['recommendation_status']} | "
            f"{'PASS' if audit['passed'] else 'FAIL'}"
        )

    print()
    print("direction_check | passed")
    for audit in direction_audits:
        print(
            f"{audit['check_id']} | "
            f"{'PASS' if audit['passed'] else 'FAIL'}"
        )

    all_passed = all(
        bool(audit["passed"])
        for audit in (*scenario_audits, *direction_audits)
    )
    print()
    print(f"Overall: {'PASS' if all_passed else 'FAIL'}")
    print("Results indicate coherence with the current model, not future outcomes.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run controlled coherence checks for pre-round Machine EV."
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run one short structural scenario instead of the full audit.",
    )
    args = parser.parse_args(argv)

    selected_ids = (
        SMOKE_SCENARIO_IDS
        if args.smoke
        else AUDIT_SCENARIO_IDS
    )
    scenarios = tuple(
        scenario
        for scenario in SCENARIOS
        if scenario.scenario_id in selected_ids
    )
    scenario_audits, direction_audits = run_accuracy_audit(scenarios)
    print_audit_report(scenario_audits, direction_audits)
    return 0 if all(
        bool(audit["passed"])
        for audit in (*scenario_audits, *direction_audits)
    ) else 1


def _direction_audits(
    results: Mapping[str, BenchmarkResult],
) -> list[dict[str, object]]:
    audits: list[dict[str, object]] = []

    def add_check(
        check_id: str,
        left_id: str,
        operator: str,
        right_id: str,
    ) -> None:
        if left_id not in results or right_id not in results:
            return
        left = _machine_edge(results[left_id])
        right = _machine_edge(results[right_id])
        if operator == ">":
            passed = left > right
        elif operator == "<=":
            passed = left <= right + 1e-9
        elif operator == ">=":
            passed = left + 1e-9 >= right
        else:
            raise ValueError(f"unsupported audit operator: {operator}")
        audits.append(
            {
                "check_id": check_id,
                "left": left,
                "right": right,
                "passed": passed,
            }
        )

    add_check(
        "low_cards_ev_above_high_cards_ev",
        "low_cards_removed",
        ">",
        "high_cards_removed",
    )
    add_check(
        "six_to_five_not_above_three_to_two",
        "blackjack_6_to_5",
        "<=",
        "low_cards_removed",
    )
    add_check(
        "h17_not_above_s17",
        "neutral_h17",
        "<=",
        "neutral_6_decks",
    )
    add_check(
        "surrender_not_below_no_surrender",
        "surrender_allowed",
        ">=",
        "neutral_6_decks",
    )
    return audits


def _machine_edge(result: BenchmarkResult) -> float:
    machine = result.get("machine_ev")
    if not isinstance(machine, Mapping):
        raise RuntimeError("benchmark result is missing machine_ev")
    return _finite_float(
        machine.get("estimated_next_hand_edge"),
        "estimated_next_hand_edge",
    )


def _finite_float(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{label} must be a finite number")
    return converted


def _optional_percent(value: object) -> str:
    return "-" if value is None else f"{float(value) * 100:.2f}%"


def _optional_number(value: object) -> str:
    return "-" if value is None else f"{float(value):.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
