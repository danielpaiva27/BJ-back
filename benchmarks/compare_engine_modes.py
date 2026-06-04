from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from blackjack_risk_engine.engine_core.engine_mode import ENGINE_MODE_VALUES, EngineMode
from blackjack_risk_engine.ev import analyze_hand
from blackjack_risk_engine.rules import GameRules


@dataclass(frozen=True, slots=True)
class CompareScenario:
    name: str
    label: str
    player_hand: list[str]
    dealer_upcard: str
    seen_cards: list[str]
    seed: int


@dataclass(frozen=True, slots=True)
class ModeComparisonResult:
    scenario: str
    label: str
    engine_mode: str
    simulations: int
    seed: int
    elapsed_s: float
    engine_elapsed_ms: float
    analysis_method: str
    best_action: str
    action_evs: dict[str, float]
    deterministic_actions: list[str]
    monte_carlo_actions: list[str]
    unsupported_actions: list[str]
    simulations_used: int
    ev_delta_vs_hybrid: dict[str, float]
    best_action_matches_hybrid: bool | None


SCENARIOS = (
    CompareScenario(
        name="A",
        label="hard 16 vs dealer 10",
        player_hand=["10", "6"],
        dealer_upcard="10",
        seen_cards=["2", "5", "6", "A", "10", "3", "4", "9"],
        seed=60_100,
    ),
    CompareScenario(
        name="B",
        label="soft 18 vs dealer 9",
        player_hand=["A", "7"],
        dealer_upcard="9",
        seen_cards=[],
        seed=60_200,
    ),
    CompareScenario(
        name="C",
        label="hard 11 vs dealer 6",
        player_hand=["5", "6"],
        dealer_upcard="6",
        seen_cards=[],
        seed=60_300,
    ),
    CompareScenario(
        name="D",
        label="pair 8s vs dealer 10",
        player_hand=["8", "8"],
        dealer_upcard="10",
        seen_cards=[],
        seed=60_400,
    ),
    CompareScenario(
        name="E",
        label="natural blackjack vs dealer 9",
        player_hand=["A", "10"],
        dealer_upcard="9",
        seen_cards=[],
        seed=60_500,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare blackjack engine modes on fixed scenarios.")
    parser.add_argument(
        "--simulations",
        type=int,
        default=5_000,
        help="Simulations per action for modes that use Monte Carlo. Default: 5000.",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=ENGINE_MODE_VALUES,
        default=list(ENGINE_MODE_VALUES),
        help="Engine modes to compare. Defaults to all modes.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON.",
    )
    return parser.parse_args()


def run_mode(
    scenario: CompareScenario,
    mode: EngineMode,
    simulations: int,
    rules: GameRules,
    hybrid_reference: dict[str, float] | None,
    hybrid_best_action: str | None,
) -> ModeComparisonResult:
    seed = scenario.seed + simulations
    start = time.perf_counter()
    result = analyze_hand(
        player_hand=scenario.player_hand,
        dealer_up_card=scenario.dealer_upcard,
        seen_cards=scenario.seen_cards,
        rules=rules,
        simulations=simulations,
        seed=seed,
        engine_mode=mode,
    )
    elapsed_s = time.perf_counter() - start
    action_evs = {action["action"]: action["ev"] for action in result["actions"]}
    ev_delta = (
        {
            action: action_evs[action] - hybrid_reference[action]
            for action in sorted(set(action_evs) & set(hybrid_reference))
        }
        if hybrid_reference is not None
        else {}
    )

    return ModeComparisonResult(
        scenario=scenario.name,
        label=scenario.label,
        engine_mode=mode,
        simulations=simulations,
        seed=seed,
        elapsed_s=round(elapsed_s, 6),
        engine_elapsed_ms=result["metadata"]["elapsed_ms"],
        analysis_method=result["metadata"]["analysis_method"],
        best_action=result["recommendation"]["best_action"],
        action_evs=action_evs,
        deterministic_actions=result["metadata"]["deterministic_actions"],
        monte_carlo_actions=result["metadata"]["monte_carlo_fallback_actions"],
        unsupported_actions=result["metadata"]["unsupported_actions"],
        simulations_used=result["metadata"]["simulations_used"],
        ev_delta_vs_hybrid=ev_delta,
        best_action_matches_hybrid=(
            result["recommendation"]["best_action"] == hybrid_best_action
            if hybrid_best_action is not None
            else None
        ),
    )


def compare_modes(scenario: CompareScenario, modes: tuple[EngineMode, ...], simulations: int) -> list[ModeComparisonResult]:
    rules = GameRules()
    hybrid_reference: dict[str, float] | None = None
    hybrid_best_action: str | None = None
    results: list[ModeComparisonResult] = []

    if "hybrid" in modes:
        hybrid_result = run_mode(
            scenario=scenario,
            mode="hybrid",
            simulations=simulations,
            rules=rules,
            hybrid_reference=None,
            hybrid_best_action=None,
        )
        hybrid_reference = hybrid_result.action_evs
        hybrid_best_action = hybrid_result.best_action
        results.append(hybrid_result)

    for mode in modes:
        if mode == "hybrid":
            continue
        results.append(
            run_mode(
                scenario=scenario,
                mode=mode,
                simulations=simulations,
                rules=rules,
                hybrid_reference=hybrid_reference,
                hybrid_best_action=hybrid_best_action,
            )
        )

    return sorted(results, key=lambda item: ENGINE_MODE_VALUES.index(item.engine_mode))  # type: ignore[arg-type]


def print_report(results: list[ModeComparisonResult]) -> None:
    print("blackjack-risk-engine engine mode comparison")
    print()
    current_scenario = ""
    for result in results:
        if result.scenario != current_scenario:
            current_scenario = result.scenario
            print(f"Scenario {result.scenario} - {result.label}")
        evs = ", ".join(f"{action}={ev:.5f}" for action, ev in result.action_evs.items())
        deltas = ", ".join(f"{action}={delta:+.5f}" for action, delta in result.ev_delta_vs_hybrid.items())
        print(
            f"  mode={result.engine_mode} method={result.analysis_method} "
            f"best={result.best_action} time={result.elapsed_s:.6f}s "
            f"simulations_used={result.simulations_used}"
        )
        print(f"    evs={evs}")
        if deltas:
            print(f"    delta_vs_hybrid={deltas}")
        if result.unsupported_actions:
            print(f"    unsupported={result.unsupported_actions}")
    print()


def main() -> int:
    args = parse_args()
    if args.simulations <= 0:
        raise ValueError("simulations must be greater than zero")

    modes = tuple(args.modes)
    results = [
        result
        for scenario in SCENARIOS
        for result in compare_modes(scenario, modes, args.simulations)
    ]

    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        print_report(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
