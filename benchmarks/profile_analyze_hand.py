from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
from pathlib import Path


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from blackjack_risk_engine.ev import analyze_hand
from blackjack_risk_engine.rules import GameRules


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile one heavy analyze_hand scenario with cProfile/pstats.",
    )
    parser.add_argument(
        "--scenario",
        choices=("hard16", "split88"),
        default="hard16",
        help="Scenario to profile. hard16 is mostly deterministic; split88 exercises Monte Carlo fallback.",
    )
    parser.add_argument(
        "--simulations",
        type=int,
        default=100_000,
        help="Simulations per legal action for the profiled scenario. Default: 100000.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=120_100,
        help="Seed for the profiled scenario.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("profile.out"),
        help="Path to save cProfile stats. Default: profile.out.",
    )
    return parser.parse_args()


def print_stats(profile: cProfile.Profile, sort_by: str, title: str) -> None:
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).strip_dirs().sort_stats(sort_by).print_stats(20)
    print(title)
    print(stream.getvalue())


def format_function(function_key: tuple[str, int, str]) -> str:
    filename, line_number, function_name = function_key
    return f"{Path(filename).name}:{line_number}({function_name})"


def print_bottleneck_summary(profile: cProfile.Profile) -> None:
    stats = pstats.Stats(profile)
    cumulative = sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)
    internal = sorted(stats.stats.items(), key=lambda item: item[1][2], reverse=True)

    print("Likely bottlenecks by cumulative time")
    for index, (function_key, values) in enumerate(cumulative[:5], start=1):
        primitive_calls, total_calls, internal_time, cumulative_time, _callers = values
        print(
            f"{index}. {format_function(function_key)} "
            f"cumtime={cumulative_time:.6f}s tottime={internal_time:.6f}s "
            f"calls={primitive_calls}/{total_calls}"
        )

    print()
    print("Likely bottlenecks by internal time")
    for index, (function_key, values) in enumerate(internal[:5], start=1):
        primitive_calls, total_calls, internal_time, cumulative_time, _callers = values
        print(
            f"{index}. {format_function(function_key)} "
            f"tottime={internal_time:.6f}s cumtime={cumulative_time:.6f}s "
            f"calls={primitive_calls}/{total_calls}"
        )


def main() -> int:
    args = parse_args()
    scenarios = {
        "hard16": {
            "label": "hard 16 vs dealer 10",
            "player_hand": ["10", "6"],
            "dealer_up_card": "10",
            "seen_cards": ["2", "5", "6", "A", "10", "3", "4", "9"],
        },
        "split88": {
            "label": "pair 8s vs dealer 10",
            "player_hand": ["8", "8"],
            "dealer_up_card": "10",
            "seen_cards": [],
        },
    }
    selected = scenarios[args.scenario]
    scenario = {
        "player_hand": selected["player_hand"],
        "dealer_up_card": selected["dealer_up_card"],
        "seen_cards": selected["seen_cards"],
        "rules": GameRules(),
        "simulations": args.simulations,
        "seed": args.seed,
    }

    profile = cProfile.Profile()
    profile.enable()
    result = analyze_hand(**scenario)
    profile.disable()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    profile.dump_stats(args.output)

    action_evs = ", ".join(f"{action['action']}: {action['ev']:.5f}" for action in result["actions"])
    print("blackjack-risk-engine analyze_hand profile")
    print(f"profile_output={args.output.resolve()}")
    print(f"scenario={selected['label']} simulations={args.simulations} seed={args.seed}")
    print(
        f"engine_mode={result['metadata']['engine_mode']} "
        f"analysis_method={result['metadata']['analysis_method']} "
        f"simulations_used={result['metadata']['simulations_used']}"
    )
    print(f"best_action={result['recommendation']['best_action']}")
    print(f"engine_reported_time_ms={result['metadata']['execution_time_ms']:.3f}")
    print(f"evs={{{action_evs}}}")
    print()

    print_stats(profile, "cumulative", "Top 20 functions by cumulative time")
    print_stats(profile, "tottime", "Top 20 functions by internal time")
    print_bottleneck_summary(profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
