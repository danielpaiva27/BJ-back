from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from blackjack_risk_engine.engine_core.adapters import build_core_state_from_inputs, ranks_to_cards
from blackjack_risk_engine.engine_core.action_ev import calculate_action_evs_deterministic
from blackjack_risk_engine.engine_core.dealer_dp import (
    dealer_distribution_cache_clear,
    dealer_outcome_distribution,
    natural_blackjack_stand_ev,
    stand_ev_from_distribution,
)
from blackjack_risk_engine.engine_core.hand import evaluate_hand_from_ranks
from blackjack_risk_engine.engine_core.monte_carlo_analysis import MonteCarloConfig, monte_carlo_analysis
from blackjack_risk_engine.engine_core.state import remaining_ordered_ranks_for_state
from blackjack_risk_engine.ev import analyze_hand
from blackjack_risk_engine.rules import GameRules
from blackjack_risk_engine.simulation import simulate_round


DEFAULT_SIMULATION_COUNTS = (10_000, 50_000, 100_000)


@dataclass(frozen=True, slots=True)
class BenchmarkScenario:
    name: str
    label: str
    player_hand: list[str]
    dealer_upcard: str
    seen_cards: list[str]
    seed: int


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    scenario: str
    label: str
    player_hand: list[str]
    dealer_upcard: str
    seen_cards: list[str]
    simulations: int
    seed: int
    repeats: int
    total_time_s: float
    average_time_s: float
    engine_time_ms: float
    engine_mode: str
    analysis_method: str
    simulations_used: int
    hand_total: int
    is_soft: bool
    is_blackjack: bool
    best_action: str
    basic_strategy_action: str
    confidence: float
    action_evs: dict[str, float]


@dataclass(frozen=True, slots=True)
class DealerDpBenchmarkResult:
    scenario: str
    label: str
    dealer_upcard: str
    deck_cards_remaining: int
    dealer_hits_soft_17: bool
    cold_time_s: float
    cached_average_time_s: float
    cached_repeats: int
    distribution: dict[str, float]
    stand_ev_dp: float
    stand_ev_monte_carlo: float
    stand_monte_carlo_simulations: int
    stand_monte_carlo_time_s: float


@dataclass(frozen=True, slots=True)
class ActionEvBenchmarkResult:
    scenario: str
    label: str
    cold_time_s: float
    cached_average_time_s: float
    cached_repeats: int
    cache_states: int
    actions: dict[str, float]
    unsupported_actions: list[str]


@dataclass(frozen=True, slots=True)
class MonteCarloComparisonResult:
    scenario: str
    label: str
    action: str
    simulations: int
    seed: int
    legacy_time_s: float
    optimized_single_time_s: float
    optimized_parallel_time_s: float
    legacy_ev: float
    optimized_single_ev: float
    optimized_parallel_ev: float
    single_speedup: float
    parallel_speedup: float
    single_ev_delta: float
    parallel_ev_delta: float
    parallel_used: bool
    parallel_chunks: int


@dataclass(slots=True)
class BenchmarkDeck:
    cards: list

    def draw(self):
        if not self.cards:
            raise IndexError("cannot draw from an empty benchmark deck")
        return self.cards.pop()


SCENARIOS = (
    BenchmarkScenario(
        name="A",
        label="hard 16 vs dealer 10",
        player_hand=["10", "6"],
        dealer_upcard="10",
        seen_cards=["2", "5", "6", "A", "10", "3", "4", "9"],
        seed=20_100,
    ),
    BenchmarkScenario(
        name="B",
        label="soft 18 vs dealer 9",
        player_hand=["A", "7"],
        dealer_upcard="9",
        seen_cards=[],
        seed=20_200,
    ),
    BenchmarkScenario(
        name="C",
        label="hard 11 vs dealer 6",
        player_hand=["5", "6"],
        dealer_upcard="6",
        seen_cards=[],
        seed=20_300,
    ),
    BenchmarkScenario(
        name="D",
        label="pair 8s vs dealer 10",
        player_hand=["8", "8"],
        dealer_upcard="10",
        seen_cards=[],
        seed=20_400,
    ),
    BenchmarkScenario(
        name="E",
        label="natural blackjack vs dealer 9",
        player_hand=["A", "10"],
        dealer_upcard="9",
        seen_cards=[],
        seed=20_500,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark fixed analyze_hand and deterministic EV scenarios.",
    )
    parser.add_argument(
        "--simulations",
        nargs="+",
        type=int,
        default=list(DEFAULT_SIMULATION_COUNTS),
        help="Simulation counts to run for each scenario. Defaults: 10000 50000 100000.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of repeated analyses per scenario/count for timing averages.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of the human-readable report.",
    )
    parser.add_argument(
        "--dealer-dp-repeat",
        type=int,
        default=1000,
        help="Cached dealer DP repetitions per scenario. Default: 1000.",
    )
    parser.add_argument(
        "--stand-compare-simulations",
        type=int,
        default=10_000,
        help="Monte Carlo stand simulations for DP comparison per scenario. Use 0 to skip. Default: 10000.",
    )
    parser.add_argument(
        "--monte-carlo-compare-simulations",
        type=int,
        default=20_000,
        help="Simulations for legacy vs optimized Monte Carlo fallback comparison. Use 0 to skip. Default: 20000.",
    )
    parser.add_argument(
        "--monte-carlo-chunk-size",
        type=int,
        default=10_000,
        help="Chunk size used by optimized Monte Carlo benchmark. Default: 10000.",
    )
    parser.add_argument(
        "--parallel-workers",
        type=int,
        default=2,
        help="Workers used by the parallel Monte Carlo benchmark. Default: 2.",
    )
    return parser.parse_args()


def run_benchmark(
    scenario: BenchmarkScenario,
    simulations: int,
    repeats: int,
    rules: GameRules,
) -> BenchmarkResult:
    if simulations <= 0:
        raise ValueError("simulations must be greater than zero")
    if repeats <= 0:
        raise ValueError("repeat must be greater than zero")

    seed = scenario.seed + simulations
    durations: list[float] = []
    result: dict | None = None

    for _ in range(repeats):
        start = time.perf_counter()
        result = analyze_hand(
            player_hand=scenario.player_hand,
            dealer_up_card=scenario.dealer_upcard,
            seen_cards=scenario.seen_cards,
            rules=rules,
            simulations=simulations,
            seed=seed,
        )
        durations.append(time.perf_counter() - start)

    if result is None:
        raise RuntimeError("benchmark did not run")

    total_time_s = sum(durations)
    actions = result.get("actions", [])
    action_evs = {action["action"]: action["ev"] for action in actions}
    recommendation = result["recommendation"]
    hand_analysis = result["hand_analysis"]

    return BenchmarkResult(
        scenario=scenario.name,
        label=scenario.label,
        player_hand=scenario.player_hand,
        dealer_upcard=scenario.dealer_upcard,
        seen_cards=scenario.seen_cards,
        simulations=simulations,
        seed=seed,
        repeats=repeats,
        total_time_s=round(total_time_s, 6),
        average_time_s=round(total_time_s / repeats, 6),
        engine_time_ms=result["metadata"]["execution_time_ms"],
        engine_mode=result["metadata"]["engine_mode"],
        analysis_method=result["metadata"]["analysis_method"],
        simulations_used=result["metadata"]["simulations_used"],
        hand_total=hand_analysis["total"],
        is_soft=hand_analysis["is_soft"],
        is_blackjack=hand_analysis["is_blackjack"],
        best_action=recommendation["best_action"],
        basic_strategy_action=recommendation["basic_strategy_action"],
        confidence=recommendation["confidence"],
        action_evs=action_evs,
    )


def format_action_evs(action_evs: dict[str, float]) -> str:
    return ", ".join(f"{action}={ev:.5f}" for action, ev in action_evs.items())


def run_dealer_dp_benchmark(
    scenario: BenchmarkScenario,
    rules: GameRules,
    cached_repeats: int,
    stand_compare_simulations: int,
) -> DealerDpBenchmarkResult:
    if cached_repeats <= 0:
        raise ValueError("dealer-dp-repeat must be greater than zero")
    if stand_compare_simulations < 0:
        raise ValueError("stand-compare-simulations cannot be negative")

    state = build_core_state_from_inputs(
        player_hand=scenario.player_hand,
        dealer_up_card=scenario.dealer_upcard,
        seen_cards=scenario.seen_cards,
        rules=rules,
    )
    player = evaluate_hand_from_ranks(state.player_ranks)

    dealer_distribution_cache_clear()
    cold_start = time.perf_counter()
    distribution = dealer_outcome_distribution(
        dealer_upcard_rank=state.dealer_upcard_rank,
        deck_counts=state.deck_counts,
        dealer_hits_soft_17=rules.dealer_hits_soft_17,
    )
    cold_time_s = time.perf_counter() - cold_start

    cached_start = time.perf_counter()
    for _ in range(cached_repeats):
        dealer_outcome_distribution(
            dealer_upcard_rank=state.dealer_upcard_rank,
            deck_counts=state.deck_counts,
            dealer_hits_soft_17=rules.dealer_hits_soft_17,
        )
    cached_average_time_s = (time.perf_counter() - cached_start) / cached_repeats

    if player.is_blackjack:
        stand_ev_dp = natural_blackjack_stand_ev(
            dealer_upcard_rank=state.dealer_upcard_rank,
            deck_counts=state.deck_counts,
            blackjack_payout_multiplier=rules.blackjack_payout_multiplier,
        ).expected_value
    else:
        stand_ev_dp = stand_ev_from_distribution(player.total, distribution).expected_value

    stand_monte_carlo_start = time.perf_counter()
    stand_ev_monte_carlo = (
        simulate_stand_ev_monte_carlo(scenario, rules, stand_compare_simulations)
        if stand_compare_simulations
        else 0.0
    )
    stand_monte_carlo_time_s = time.perf_counter() - stand_monte_carlo_start

    return DealerDpBenchmarkResult(
        scenario=scenario.name,
        label=scenario.label,
        dealer_upcard=scenario.dealer_upcard,
        deck_cards_remaining=state.cards_remaining,
        dealer_hits_soft_17=rules.dealer_hits_soft_17,
        cold_time_s=round(cold_time_s, 9),
        cached_average_time_s=round(cached_average_time_s, 12),
        cached_repeats=cached_repeats,
        distribution={
            "17": distribution[0],
            "18": distribution[1],
            "19": distribution[2],
            "20": distribution[3],
            "21": distribution[4],
            "bust": distribution[5],
        },
        stand_ev_dp=stand_ev_dp,
        stand_ev_monte_carlo=stand_ev_monte_carlo,
        stand_monte_carlo_simulations=stand_compare_simulations,
        stand_monte_carlo_time_s=round(stand_monte_carlo_time_s, 6),
    )


def run_action_ev_benchmark(
    scenario: BenchmarkScenario,
    rules: GameRules,
    cached_repeats: int,
) -> ActionEvBenchmarkResult:
    if cached_repeats <= 0:
        raise ValueError("dealer-dp-repeat must be greater than zero")

    state = build_core_state_from_inputs(
        player_hand=scenario.player_hand,
        dealer_up_card=scenario.dealer_upcard,
        seen_cards=scenario.seen_cards,
        rules=rules,
    )
    legal_actions = ("hit", "stand", "double", "split") if scenario.player_hand == ["8", "8"] else ("hit", "stand", "double")
    if scenario.player_hand == ["A", "10"]:
        legal_actions = ("stand",)

    cold_start = time.perf_counter()
    ranking = calculate_action_evs_deterministic(state, legal_actions)
    cold_time_s = time.perf_counter() - cold_start

    cached_start = time.perf_counter()
    for _ in range(cached_repeats):
        calculate_action_evs_deterministic(state, legal_actions)
    cached_average_time_s = (time.perf_counter() - cached_start) / cached_repeats

    return ActionEvBenchmarkResult(
        scenario=scenario.name,
        label=scenario.label,
        cold_time_s=round(cold_time_s, 9),
        cached_average_time_s=round(cached_average_time_s, 12),
        cached_repeats=cached_repeats,
        cache_states=ranking.cache_states,
        actions={action.action: action.ev for action in ranking.actions},
        unsupported_actions=list(ranking.unsupported_actions),
    )


def simulate_stand_ev_monte_carlo(
    scenario: BenchmarkScenario,
    rules: GameRules,
    simulations: int,
) -> float:
    if simulations <= 0:
        return 0.0

    state = build_core_state_from_inputs(
        player_hand=scenario.player_hand,
        dealer_up_card=scenario.dealer_upcard,
        seen_cards=scenario.seen_cards,
        rules=rules,
    )
    base_cards = ranks_to_cards(remaining_ordered_ranks_for_state(state))
    rng = random.Random(scenario.seed + simulations + 1_000_000)
    total_outcome = 0.0

    for _ in range(simulations):
        cards = list(base_cards)
        rng.shuffle(cards)
        result = simulate_round(
            player_hand=scenario.player_hand,
            dealer_up_card=scenario.dealer_upcard,
            deck=BenchmarkDeck(cards),
            rules=rules,
            action="stand",
        )
        total_outcome += result.outcome

    return total_outcome / simulations


def run_monte_carlo_comparison(
    scenario: BenchmarkScenario,
    rules: GameRules,
    simulations: int,
    chunk_size: int,
    parallel_workers: int,
) -> MonteCarloComparisonResult:
    if simulations <= 0:
        raise ValueError("monte-carlo-compare-simulations must be greater than zero")
    if chunk_size <= 0:
        raise ValueError("monte-carlo-chunk-size must be greater than zero")
    if parallel_workers <= 0:
        raise ValueError("parallel-workers must be greater than zero")

    action = "split"
    seed = scenario.seed + simulations + 2_000_000
    state = build_core_state_from_inputs(
        player_hand=scenario.player_hand,
        dealer_up_card=scenario.dealer_upcard,
        seen_cards=scenario.seen_cards,
        rules=rules,
    )

    legacy_start = time.perf_counter()
    legacy_ev = simulate_action_ev_legacy_monte_carlo(
        scenario=scenario,
        rules=rules,
        action=action,
        simulations=simulations,
        seed=seed,
    )
    legacy_time_s = time.perf_counter() - legacy_start

    single_start = time.perf_counter()
    single_result = monte_carlo_analysis(
        state=state,
        action=action,
        simulations=simulations,
        seed=seed,
        config=MonteCarloConfig(
            parallel_enabled=False,
            simulation_chunk_size=chunk_size,
        ),
    )
    single_time_s = time.perf_counter() - single_start

    parallel_start = time.perf_counter()
    parallel_result = monte_carlo_analysis(
        state=state,
        action=action,
        simulations=simulations,
        seed=seed,
        config=MonteCarloConfig(
            parallel_enabled=True,
            parallel_threshold=1,
            simulation_chunk_size=chunk_size,
            max_workers=parallel_workers,
        ),
    )
    parallel_time_s = time.perf_counter() - parallel_start

    single_ev = single_result.stats.expected_value
    parallel_ev = parallel_result.stats.expected_value
    return MonteCarloComparisonResult(
        scenario=scenario.name,
        label=scenario.label,
        action=action,
        simulations=simulations,
        seed=seed,
        legacy_time_s=round(legacy_time_s, 6),
        optimized_single_time_s=round(single_time_s, 6),
        optimized_parallel_time_s=round(parallel_time_s, 6),
        legacy_ev=legacy_ev,
        optimized_single_ev=single_ev,
        optimized_parallel_ev=parallel_ev,
        single_speedup=round(legacy_time_s / single_time_s, 3) if single_time_s > 0 else 0.0,
        parallel_speedup=round(legacy_time_s / parallel_time_s, 3) if parallel_time_s > 0 else 0.0,
        single_ev_delta=single_ev - legacy_ev,
        parallel_ev_delta=parallel_ev - legacy_ev,
        parallel_used=parallel_result.used_parallel,
        parallel_chunks=parallel_result.chunk_count,
    )


def simulate_action_ev_legacy_monte_carlo(
    scenario: BenchmarkScenario,
    rules: GameRules,
    action: str,
    simulations: int,
    seed: int,
) -> float:
    state = build_core_state_from_inputs(
        player_hand=scenario.player_hand,
        dealer_up_card=scenario.dealer_upcard,
        seen_cards=scenario.seen_cards,
        rules=rules,
    )
    base_cards = ranks_to_cards(remaining_ordered_ranks_for_state(state))
    rng = random.Random(seed)
    total_outcome = 0.0

    for _ in range(simulations):
        cards = list(base_cards)
        rng.shuffle(cards)
        result = simulate_round(
            player_hand=scenario.player_hand,
            dealer_up_card=scenario.dealer_upcard,
            deck=BenchmarkDeck(cards),
            rules=rules,
            action=action,
        )
        total_outcome += result.outcome

    return total_outcome / simulations


def print_human_report(
    results: list[BenchmarkResult],
    dealer_results: list[DealerDpBenchmarkResult],
    action_ev_results: list[ActionEvBenchmarkResult],
    monte_carlo_results: list[MonteCarloComparisonResult],
) -> None:
    print("blackjack-risk-engine analyze_hand benchmark")
    print(f"scenario_count={len(SCENARIOS)}")
    print()

    for result in results:
        print(f"Scenario {result.scenario} - {result.label}")
        print(f"  player_hand={result.player_hand} dealer_upcard={result.dealer_upcard}")
        print(f"  seen_cards={result.seen_cards}")
        print(f"  simulations={result.simulations} seed={result.seed} repeats={result.repeats}")
        print(f"  total_time_s={result.total_time_s:.6f}")
        print(f"  average_time_s={result.average_time_s:.6f}")
        print(
            f"  engine_reported_time_ms={result.engine_time_ms:.3f} "
            f"engine_mode={result.engine_mode} method={result.analysis_method} "
            f"simulations_used={result.simulations_used}"
        )
        print(
            "  engine_response="
            f"total={result.hand_total} soft={result.is_soft} "
            f"blackjack={result.is_blackjack} best_action={result.best_action} "
            f"basic_strategy={result.basic_strategy_action} confidence={result.confidence:.4f}"
        )
        print(f"  evs={format_action_evs(result.action_evs)}")
        print()

    print("dealer_outcome_distribution benchmark")
    print()

    for result in dealer_results:
        distribution = ", ".join(f"{key}={value:.6f}" for key, value in result.distribution.items())
        print(f"Scenario {result.scenario} - {result.label}")
        print(f"  dealer_upcard={result.dealer_upcard} cards_remaining={result.deck_cards_remaining}")
        print(f"  dealer_hits_soft_17={result.dealer_hits_soft_17}")
        print(f"  cold_time_s={result.cold_time_s:.9f}")
        print(
            f"  cached_average_time_s={result.cached_average_time_s:.12f} "
            f"repeats={result.cached_repeats}"
        )
        print(f"  distribution={distribution}")
        print(
            f"  stand_ev_dp={result.stand_ev_dp:.6f} "
            f"stand_ev_monte_carlo={result.stand_ev_monte_carlo:.6f} "
            f"stand_mc_simulations={result.stand_monte_carlo_simulations} "
            f"stand_mc_time_s={result.stand_monte_carlo_time_s:.6f}"
        )
        print()

    print("deterministic action EV benchmark")
    print()

    for result in action_ev_results:
        evs = ", ".join(f"{action}={ev:.6f}" for action, ev in result.actions.items())
        print(f"Scenario {result.scenario} - {result.label}")
        print(f"  cold_time_s={result.cold_time_s:.9f}")
        print(
            f"  cached_average_time_s={result.cached_average_time_s:.12f} "
            f"repeats={result.cached_repeats}"
        )
        print(f"  cache_states={result.cache_states}")
        print(f"  evs={evs}")
        print(f"  unsupported_actions={result.unsupported_actions}")
        print()

    if monte_carlo_results:
        print("Monte Carlo fallback benchmark")
        print()

    for result in monte_carlo_results:
        print(f"Scenario {result.scenario} - {result.label}")
        print(f"  action={result.action} simulations={result.simulations} seed={result.seed}")
        print(
            f"  legacy_time_s={result.legacy_time_s:.6f} "
            f"optimized_single_time_s={result.optimized_single_time_s:.6f} "
            f"optimized_parallel_time_s={result.optimized_parallel_time_s:.6f}"
        )
        print(
            f"  single_speedup={result.single_speedup:.3f}x "
            f"parallel_speedup={result.parallel_speedup:.3f}x "
            f"parallel_used={result.parallel_used} chunks={result.parallel_chunks}"
        )
        print(
            f"  legacy_ev={result.legacy_ev:.6f} "
            f"optimized_single_ev={result.optimized_single_ev:.6f} "
            f"optimized_parallel_ev={result.optimized_parallel_ev:.6f}"
        )
        print(
            f"  single_ev_delta={result.single_ev_delta:.6f} "
            f"parallel_ev_delta={result.parallel_ev_delta:.6f}"
        )
        print()


def main() -> int:
    args = parse_args()
    rules = GameRules()
    results = [
        run_benchmark(scenario, simulations, args.repeat, rules)
        for scenario in SCENARIOS
        for simulations in args.simulations
    ]
    dealer_results = [
        run_dealer_dp_benchmark(
            scenario,
            rules,
            args.dealer_dp_repeat,
            args.stand_compare_simulations,
        )
        for scenario in SCENARIOS
    ]
    action_ev_results = [
        run_action_ev_benchmark(scenario, rules, args.dealer_dp_repeat)
        for scenario in SCENARIOS
    ]
    monte_carlo_results = (
        [
            run_monte_carlo_comparison(
                scenario=next(scenario for scenario in SCENARIOS if scenario.name == "D"),
                rules=rules,
                simulations=args.monte_carlo_compare_simulations,
                chunk_size=args.monte_carlo_chunk_size,
                parallel_workers=args.parallel_workers,
            )
        ]
        if args.monte_carlo_compare_simulations
        else []
    )

    if args.json:
        print(
            json.dumps(
                {
                    "analyze_hand": [asdict(result) for result in results],
                    "dealer_dp": [asdict(result) for result in dealer_results],
                    "action_ev": [asdict(result) for result in action_ev_results],
                    "monte_carlo": [asdict(result) for result in monte_carlo_results],
                },
                indent=2,
            )
        )
    else:
        print_human_report(results, dealer_results, action_ev_results, monte_carlo_results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
