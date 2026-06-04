from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from blackjack_risk_engine.engine_core.engine_mode import EngineMode
from blackjack_risk_engine.ev import analyze_hand
from blackjack_risk_engine.rules import GameRules


MODE_ORDER: tuple[EngineMode, ...] = ("deterministic", "hybrid", "monte_carlo", "legacy")


@dataclass(frozen=True, slots=True)
class AccuracyScenario:
    name: str
    label: str
    player_hand: list[str]
    dealer_upcard: str
    seen_cards: list[str]
    seed: int


@dataclass(frozen=True, slots=True)
class ActionEvSummary:
    ev: float
    standard_error: float
    confidence_interval_95: list[float]


@dataclass(frozen=True, slots=True)
class ModeAccuracyResult:
    scenario: str
    label: str
    engine_mode: str
    best_action: str
    action_evs: dict[str, ActionEvSummary]
    analysis_method: str
    simulations_used: int
    elapsed_ms: float
    wall_elapsed_ms: float
    deterministic_actions: list[str]
    monte_carlo_actions: list[str]
    unsupported_actions: list[str]


@dataclass(frozen=True, slots=True)
class ActionAccuracyComparison:
    scenario: str
    action: str
    deterministic_vs_hybrid_delta: float | None
    hybrid_vs_monte_carlo_delta: float | None
    legacy_vs_hybrid_delta: float | None
    monte_carlo_standard_error: float | None
    hybrid_standard_error: float | None
    monte_carlo_tolerance: float | None
    monte_carlo_within_tolerance: bool | None


@dataclass(frozen=True, slots=True)
class ScenarioAccuracyReport:
    scenario: AccuracyScenario
    modes: list[ModeAccuracyResult]
    comparisons: list[ActionAccuracyComparison]


SCENARIOS = (
    AccuracyScenario(
        name="A",
        label="hard 16 vs dealer 10",
        player_hand=["10", "6"],
        dealer_upcard="10",
        seen_cards=[],
        seed=71_100,
    ),
    AccuracyScenario(
        name="B",
        label="soft 18 vs dealer 9",
        player_hand=["A", "7"],
        dealer_upcard="9",
        seen_cards=[],
        seed=71_200,
    ),
    AccuracyScenario(
        name="C",
        label="hard 11 vs dealer 6",
        player_hand=["5", "6"],
        dealer_upcard="6",
        seen_cards=[],
        seed=71_300,
    ),
    AccuracyScenario(
        name="D",
        label="pair 8,8 vs dealer 10",
        player_hand=["8", "8"],
        dealer_upcard="10",
        seen_cards=[],
        seed=71_400,
    ),
    AccuracyScenario(
        name="E",
        label="natural blackjack vs dealer 9",
        player_hand=["A", "10"],
        dealer_upcard="9",
        seen_cards=[],
        seed=71_500,
    ),
    AccuracyScenario(
        name="F",
        label="hard 12 vs dealer 2",
        player_hand=["10", "2"],
        dealer_upcard="2",
        seen_cards=[],
        seed=71_600,
    ),
    AccuracyScenario(
        name="G",
        label="hard 20 vs dealer 10",
        player_hand=["10", "10"],
        dealer_upcard="10",
        seen_cards=[],
        seed=71_700,
    ),
    AccuracyScenario(
        name="H",
        label="hard 9 vs dealer 3",
        player_hand=["4", "5"],
        dealer_upcard="3",
        seen_cards=[],
        seed=71_800,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit blackjack engine mode accuracy on deterministic and statistical scenarios."
    )
    parser.add_argument(
        "--simulations",
        type=int,
        default=10_000,
        help="Monte Carlo simulations per action. Default: 10000.",
    )
    parser.add_argument(
        "--monte-carlo-tolerance",
        type=float,
        default=0.02,
        help="Minimum absolute EV tolerance for Monte Carlo comparisons. Default: 0.02.",
    )
    parser.add_argument(
        "--confidence-z",
        type=float,
        default=2.58,
        help="Z multiplier for Monte Carlo standard-error tolerance. Default: 2.58 (~99%%).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON.",
    )
    return parser.parse_args()


def run_mode(scenario: AccuracyScenario, mode: EngineMode, simulations: int) -> ModeAccuracyResult:
    start = time.perf_counter()
    result = analyze_hand(
        player_hand=scenario.player_hand,
        dealer_up_card=scenario.dealer_upcard,
        seen_cards=scenario.seen_cards,
        rules=GameRules(),
        simulations=simulations,
        seed=scenario.seed,
        engine_mode=mode,
    )
    wall_elapsed_ms = (time.perf_counter() - start) * 1000
    action_evs = {
        action["action"]: ActionEvSummary(
            ev=action["ev"],
            standard_error=action["standard_error"],
            confidence_interval_95=action["confidence_interval_95"],
        )
        for action in result["actions"]
    }

    return ModeAccuracyResult(
        scenario=scenario.name,
        label=scenario.label,
        engine_mode=mode,
        best_action=result["recommendation"]["best_action"],
        action_evs=action_evs,
        analysis_method=result["metadata"]["analysis_method"],
        simulations_used=result["metadata"]["simulations_used"],
        elapsed_ms=result["metadata"]["elapsed_ms"],
        wall_elapsed_ms=round(wall_elapsed_ms, 3),
        deterministic_actions=result["metadata"]["deterministic_actions"],
        monte_carlo_actions=result["metadata"]["monte_carlo_fallback_actions"],
        unsupported_actions=result["metadata"]["unsupported_actions"],
    )


def compare_scenario(
    scenario: AccuracyScenario,
    simulations: int,
    monte_carlo_tolerance: float,
    confidence_z: float,
) -> ScenarioAccuracyReport:
    mode_results = [run_mode(scenario, mode, simulations) for mode in MODE_ORDER]
    by_mode = {result.engine_mode: result for result in mode_results}
    actions = sorted({action for result in mode_results for action in result.action_evs})
    comparisons = [
        compare_action(
            scenario=scenario.name,
            action=action,
            deterministic=by_mode["deterministic"].action_evs.get(action),
            hybrid=by_mode["hybrid"].action_evs.get(action),
            monte_carlo=by_mode["monte_carlo"].action_evs.get(action),
            legacy=by_mode["legacy"].action_evs.get(action),
            minimum_tolerance=monte_carlo_tolerance,
            confidence_z=confidence_z,
        )
        for action in actions
    ]
    return ScenarioAccuracyReport(scenario=scenario, modes=mode_results, comparisons=comparisons)


def compare_action(
    *,
    scenario: str,
    action: str,
    deterministic: ActionEvSummary | None,
    hybrid: ActionEvSummary | None,
    monte_carlo: ActionEvSummary | None,
    legacy: ActionEvSummary | None,
    minimum_tolerance: float,
    confidence_z: float,
) -> ActionAccuracyComparison:
    deterministic_vs_hybrid_delta = (
        deterministic.ev - hybrid.ev if deterministic is not None and hybrid is not None else None
    )
    hybrid_vs_monte_carlo_delta = (
        hybrid.ev - monte_carlo.ev if hybrid is not None and monte_carlo is not None else None
    )
    legacy_vs_hybrid_delta = legacy.ev - hybrid.ev if legacy is not None and hybrid is not None else None

    monte_carlo_standard_error = monte_carlo.standard_error if monte_carlo is not None else None
    hybrid_standard_error = hybrid.standard_error if hybrid is not None else None
    monte_carlo_tolerance = None
    monte_carlo_within_tolerance = None
    if hybrid_vs_monte_carlo_delta is not None and monte_carlo is not None and hybrid is not None:
        combined_se = math.sqrt(monte_carlo.standard_error**2 + hybrid.standard_error**2)
        monte_carlo_tolerance = max(minimum_tolerance, confidence_z * combined_se)
        monte_carlo_within_tolerance = abs(hybrid_vs_monte_carlo_delta) <= monte_carlo_tolerance

    return ActionAccuracyComparison(
        scenario=scenario,
        action=action,
        deterministic_vs_hybrid_delta=deterministic_vs_hybrid_delta,
        hybrid_vs_monte_carlo_delta=hybrid_vs_monte_carlo_delta,
        legacy_vs_hybrid_delta=legacy_vs_hybrid_delta,
        monte_carlo_standard_error=monte_carlo_standard_error,
        hybrid_standard_error=hybrid_standard_error,
        monte_carlo_tolerance=monte_carlo_tolerance,
        monte_carlo_within_tolerance=monte_carlo_within_tolerance,
    )


def print_report(reports: list[ScenarioAccuracyReport], simulations: int, confidence_z: float) -> None:
    print("blackjack-risk-engine accuracy comparison")
    print(f"simulations_per_monte_carlo_action={simulations}")
    print(f"monte_carlo_check=max(configured_tolerance, {confidence_z:.2f} * combined_standard_error)")
    print()

    for report in reports:
        scenario = report.scenario
        print(f"Scenario {scenario.name} - {scenario.label}")
        print(f"  player={scenario.player_hand} dealer_upcard={scenario.dealer_upcard} seen={scenario.seen_cards}")
        for mode in report.modes:
            evs = ", ".join(f"{action}={summary.ev:+.6f}" for action, summary in mode.action_evs.items())
            print(
                f"  mode={mode.engine_mode:<13} method={mode.analysis_method:<43} "
                f"best={mode.best_action:<9} elapsed_ms={mode.elapsed_ms:>8.3f} "
                f"wall_ms={mode.wall_elapsed_ms:>8.3f} simulations_used={mode.simulations_used}"
            )
            print(f"    evs={evs}")
            if mode.unsupported_actions:
                print(f"    unsupported={mode.unsupported_actions}")
            if mode.monte_carlo_actions:
                print(f"    monte_carlo_actions={mode.monte_carlo_actions}")

        print("  comparisons")
        for comparison in report.comparisons:
            det_hybrid = format_optional_delta(comparison.deterministic_vs_hybrid_delta)
            hybrid_mc = format_optional_delta(comparison.hybrid_vs_monte_carlo_delta)
            legacy_hybrid = format_optional_delta(comparison.legacy_vs_hybrid_delta)
            mc_status = (
                "n/a"
                if comparison.monte_carlo_within_tolerance is None
                else "ok"
                if comparison.monte_carlo_within_tolerance
                else "investigate"
            )
            tolerance = (
                "n/a"
                if comparison.monte_carlo_tolerance is None
                else f"{comparison.monte_carlo_tolerance:.6f}"
            )
            mc_se = (
                "n/a"
                if comparison.monte_carlo_standard_error is None
                else f"{comparison.monte_carlo_standard_error:.6f}"
            )
            print(
                f"    action={comparison.action:<9} det-hybrid={det_hybrid:<12} "
                f"hybrid-mc={hybrid_mc:<12} legacy-hybrid={legacy_hybrid:<12} "
                f"mc_se={mc_se:<10} tolerance={tolerance:<10} mc_status={mc_status}"
            )
        print()


def format_optional_delta(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.6f}"


def main() -> int:
    args = parse_args()
    if args.simulations <= 0:
        raise ValueError("simulations must be greater than zero")
    if args.monte_carlo_tolerance <= 0:
        raise ValueError("monte_carlo_tolerance must be greater than zero")
    if args.confidence_z <= 0:
        raise ValueError("confidence_z must be greater than zero")

    reports = [
        compare_scenario(
            scenario=scenario,
            simulations=args.simulations,
            monte_carlo_tolerance=args.monte_carlo_tolerance,
            confidence_z=args.confidence_z,
        )
        for scenario in SCENARIOS
    ]

    if args.json:
        print(json.dumps([asdict(report) for report in reports], indent=2))
    else:
        print_report(reports, args.simulations, args.confidence_z)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
