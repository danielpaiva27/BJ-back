from __future__ import annotations

import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from math import sqrt

from blackjack_risk_engine.engine_core.cards import CARD_VALUES, RankIndex
from blackjack_risk_engine.engine_core.hand import evaluate_hand_from_ranks, is_bust
from blackjack_risk_engine.engine_core.rules import CoreRules
from blackjack_risk_engine.engine_core.state import CoreGameState


@dataclass(frozen=True, slots=True)
class MonteCarloConfig:
    parallel_enabled: bool = False
    parallel_threshold: int = 20_000
    simulation_chunk_size: int = 10_000
    max_workers: int | None = None

    def __post_init__(self) -> None:
        if self.parallel_threshold <= 0:
            raise ValueError("parallel_threshold must be greater than zero")
        if self.simulation_chunk_size <= 0:
            raise ValueError("simulation_chunk_size must be greater than zero")
        if self.max_workers is not None and self.max_workers <= 0:
            raise ValueError("max_workers must be greater than zero")


@dataclass(frozen=True, slots=True)
class MonteCarloStats:
    simulations: int
    total_outcome: float
    total_squared_outcome: float
    wins: int
    losses: int
    pushes: int

    @property
    def expected_value(self) -> float:
        return self.total_outcome / self.simulations

    @property
    def std_dev(self) -> float:
        if self.simulations <= 1:
            return 0.0
        variance = (
            self.total_squared_outcome - (self.total_outcome * self.total_outcome / self.simulations)
        ) / (self.simulations - 1)
        return sqrt(max(variance, 0.0))


@dataclass(frozen=True, slots=True)
class MonteCarloActionResult:
    action: str
    stats: MonteCarloStats
    used_parallel: bool
    chunk_count: int
    chunk_size: int
    worker_count: int


@dataclass(frozen=True, slots=True)
class _MonteCarloJob:
    player_ranks: tuple[RankIndex, ...]
    dealer_upcard_rank: RankIndex
    deck_counts: tuple[int, ...]
    rules: CoreRules
    action: str
    simulations: int
    seed: int | None


def monte_carlo_analysis(
    state: CoreGameState,
    action: str,
    simulations: int,
    seed: int | None = None,
    config: MonteCarloConfig | None = None,
) -> MonteCarloActionResult:
    if simulations <= 0:
        raise ValueError("simulations must be greater than zero")

    active_config = config or MonteCarloConfig()
    chunks = plan_monte_carlo_chunks(simulations, active_config)
    worker_count = _effective_worker_count(active_config, len(chunks))
    used_parallel = _should_use_parallel(simulations, active_config, worker_count, len(chunks))
    seeds = _chunk_seeds(seed, len(chunks))
    jobs = tuple(
        _MonteCarloJob(
            player_ranks=state.player_ranks,
            dealer_upcard_rank=state.dealer_upcard_rank,
            deck_counts=state.deck_counts,
            rules=state.rules,
            action=action,
            simulations=chunk_size,
            seed=chunk_seed,
        )
        for chunk_size, chunk_seed in zip(chunks, seeds, strict=True)
    )

    if used_parallel:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            stats = tuple(executor.map(_simulate_chunk, jobs))
    else:
        stats = tuple(_simulate_chunk(job) for job in jobs)

    merged = _merge_stats(stats)
    return MonteCarloActionResult(
        action=action,
        stats=merged,
        used_parallel=used_parallel,
        chunk_count=len(chunks),
        chunk_size=active_config.simulation_chunk_size,
        worker_count=worker_count if used_parallel else 1,
    )


def plan_monte_carlo_chunks(simulations: int, config: MonteCarloConfig | None = None) -> tuple[int, ...]:
    if simulations <= 0:
        raise ValueError("simulations must be greater than zero")

    active_config = config or MonteCarloConfig()
    chunk_size = active_config.simulation_chunk_size
    full_chunks, remainder = divmod(simulations, chunk_size)
    chunks = [chunk_size] * full_chunks
    if remainder:
        chunks.append(remainder)
    return tuple(chunks or (simulations,))


def _chunk_seeds(seed: int | None, chunk_count: int) -> tuple[int | None, ...]:
    if chunk_count == 1:
        return (seed,)

    rng = random.Random(seed)
    return tuple(rng.randrange(2**63) for _ in range(chunk_count))


def _effective_worker_count(config: MonteCarloConfig, chunk_count: int) -> int:
    if config.max_workers is None:
        return min(chunk_count, 4)
    return min(chunk_count, config.max_workers)


def _should_use_parallel(
    simulations: int,
    config: MonteCarloConfig,
    worker_count: int,
    chunk_count: int,
) -> bool:
    return (
        config.parallel_enabled
        and simulations >= config.parallel_threshold
        and chunk_count > 1
        and worker_count > 1
    )


def _simulate_chunk(job: _MonteCarloJob) -> MonteCarloStats:
    rng = random.Random(job.seed)
    player = evaluate_hand_from_ranks(job.player_ranks)
    total_outcome = 0.0
    total_squared_outcome = 0.0
    wins = 0
    losses = 0
    pushes = 0

    for _ in range(job.simulations):
        outcome = _simulate_round_from_counts(
            player_ranks=job.player_ranks,
            player_total=player.total,
            player_soft_aces=player.soft_aces,
            player_is_blackjack=player.is_blackjack,
            dealer_upcard_rank=job.dealer_upcard_rank,
            base_deck_counts=job.deck_counts,
            rules=job.rules,
            action=job.action,
            rng=rng,
        )
        total_outcome += outcome
        total_squared_outcome += outcome * outcome
        if outcome > 0:
            wins += 1
        elif outcome < 0:
            losses += 1
        else:
            pushes += 1

    return MonteCarloStats(
        simulations=job.simulations,
        total_outcome=total_outcome,
        total_squared_outcome=total_squared_outcome,
        wins=wins,
        losses=losses,
        pushes=pushes,
    )


def _merge_stats(stats: tuple[MonteCarloStats, ...]) -> MonteCarloStats:
    simulations = sum(item.simulations for item in stats)
    return MonteCarloStats(
        simulations=simulations,
        total_outcome=sum(item.total_outcome for item in stats),
        total_squared_outcome=sum(item.total_squared_outcome for item in stats),
        wins=sum(item.wins for item in stats),
        losses=sum(item.losses for item in stats),
        pushes=sum(item.pushes for item in stats),
    )


def _simulate_round_from_counts(
    player_ranks: tuple[RankIndex, ...],
    player_total: int,
    player_soft_aces: int,
    player_is_blackjack: bool,
    dealer_upcard_rank: RankIndex,
    base_deck_counts: tuple[int, ...],
    rules: CoreRules,
    action: str,
    rng: random.Random,
) -> float:
    deck_counts = list(base_deck_counts)
    cards_remaining = sum(deck_counts)
    hole_card, cards_remaining = _draw_rank(deck_counts, cards_remaining, rng)
    dealer_total, dealer_soft_aces = _add_card_to_total_fast(0, 0, dealer_upcard_rank)
    dealer_total, dealer_soft_aces = _add_card_to_total_fast(dealer_total, dealer_soft_aces, hole_card)

    if action == "surrender":
        return -0.5

    natural_outcome = _resolve_natural_blackjack(
        player_is_blackjack=player_is_blackjack,
        dealer_total=dealer_total,
        dealer_soft_aces=dealer_soft_aces,
        dealer_card_count=2,
        rules=rules,
    )
    if natural_outcome is not None:
        return natural_outcome

    if action == "hit":
        player_total, player_soft_aces, cards_remaining = _play_strategic_hit_continuation(
            player_total=player_total,
            player_soft_aces=player_soft_aces,
            dealer_upcard_rank=dealer_upcard_rank,
            deck_counts=deck_counts,
            cards_remaining=cards_remaining,
            rng=rng,
        )
        if is_bust(player_total):
            return -1.0

    elif action == "double":
        rank, cards_remaining = _draw_rank(deck_counts, cards_remaining, rng)
        player_total, player_soft_aces = _add_card_to_total_fast(player_total, player_soft_aces, rank)
        if is_bust(player_total):
            return -2.0

    elif action == "split":
        first_total, first_soft, cards_remaining = _start_split_hand(
            split_rank=player_ranks[0],
            deck_counts=deck_counts,
            cards_remaining=cards_remaining,
            rng=rng,
        )
        second_total, second_soft, cards_remaining = _start_split_hand(
            split_rank=player_ranks[1],
            deck_counts=deck_counts,
            cards_remaining=cards_remaining,
            rng=rng,
        )
        first_total, first_soft, cards_remaining = _play_until_17_policy(
            total=first_total,
            soft_aces=first_soft,
            deck_counts=deck_counts,
            cards_remaining=cards_remaining,
            rng=rng,
        )
        second_total, second_soft, cards_remaining = _play_until_17_policy(
            total=second_total,
            soft_aces=second_soft,
            deck_counts=deck_counts,
            cards_remaining=cards_remaining,
            rng=rng,
        )

        if is_bust(first_total) and is_bust(second_total):
            return _compare_totals(first_total, dealer_total) + _compare_totals(second_total, dealer_total)

        dealer_total, dealer_soft_aces, cards_remaining = _play_dealer(
            total=dealer_total,
            soft_aces=dealer_soft_aces,
            deck_counts=deck_counts,
            cards_remaining=cards_remaining,
            dealer_hits_soft_17=rules.dealer_hits_soft_17,
            rng=rng,
        )
        return _compare_totals(first_total, dealer_total) + _compare_totals(second_total, dealer_total)

    elif action != "stand":
        raise ValueError("action must be one of: hit, stand, double, split, surrender")

    dealer_total, dealer_soft_aces, cards_remaining = _play_dealer(
        total=dealer_total,
        soft_aces=dealer_soft_aces,
        deck_counts=deck_counts,
        cards_remaining=cards_remaining,
        dealer_hits_soft_17=rules.dealer_hits_soft_17,
        rng=rng,
    )
    outcome = _compare_totals(player_total, dealer_total)
    if action == "double" and outcome != 0:
        return outcome * 2
    return float(outcome)


def _draw_rank(
    deck_counts: list[int],
    cards_remaining: int,
    rng: random.Random,
) -> tuple[RankIndex, int]:
    if cards_remaining <= 0:
        raise IndexError("cannot draw from an empty simulation deck")

    target = rng.randrange(cards_remaining)
    cumulative = 0
    for rank, count in enumerate(deck_counts):
        cumulative += count
        if target < cumulative:
            deck_counts[rank] -= 1
            return rank, cards_remaining - 1

    raise RuntimeError("failed to draw from deck counts")


def _resolve_natural_blackjack(
    player_is_blackjack: bool,
    dealer_total: int,
    dealer_soft_aces: int,
    dealer_card_count: int,
    rules: CoreRules,
) -> float | None:
    dealer_is_blackjack = dealer_card_count == 2 and dealer_total == 21 and dealer_soft_aces > 0
    if player_is_blackjack and dealer_is_blackjack:
        return 0.0
    if player_is_blackjack:
        return rules.blackjack_payout_multiplier
    if dealer_is_blackjack:
        return -1.0
    return None


def _play_strategic_hit_continuation(
    player_total: int,
    player_soft_aces: int,
    dealer_upcard_rank: RankIndex,
    deck_counts: list[int],
    cards_remaining: int,
    rng: random.Random,
) -> tuple[int, int, int]:
    rank, cards_remaining = _draw_rank(deck_counts, cards_remaining, rng)
    player_total, player_soft_aces = _add_card_to_total_fast(player_total, player_soft_aces, rank)
    while _choose_continuation_action(player_total, player_soft_aces, dealer_upcard_rank) == "hit":
        rank, cards_remaining = _draw_rank(deck_counts, cards_remaining, rng)
        player_total, player_soft_aces = _add_card_to_total_fast(player_total, player_soft_aces, rank)
    return player_total, player_soft_aces, cards_remaining


def _choose_continuation_action(total: int, soft_aces: int, dealer_upcard_rank: RankIndex) -> str:
    if is_bust(total):
        return "stand"

    dealer_value = _dealer_strategy_value(dealer_upcard_rank)
    if soft_aces > 0:
        if total <= 17:
            return "hit"
        if total == 18:
            return "stand" if 2 <= dealer_value <= 8 else "hit"
        return "stand"

    if total <= 11:
        return "hit"
    if total == 12:
        return "stand" if 4 <= dealer_value <= 6 else "hit"
    if 13 <= total <= 16:
        return "stand" if 2 <= dealer_value <= 6 else "hit"
    return "stand"


def _dealer_strategy_value(dealer_upcard_rank: RankIndex) -> int:
    return 11 if dealer_upcard_rank == 0 else CARD_VALUES[dealer_upcard_rank]


def _start_split_hand(
    split_rank: RankIndex,
    deck_counts: list[int],
    cards_remaining: int,
    rng: random.Random,
) -> tuple[int, int, int]:
    total, soft_aces = _add_card_to_total_fast(0, 0, split_rank)
    rank, cards_remaining = _draw_rank(deck_counts, cards_remaining, rng)
    total, soft_aces = _add_card_to_total_fast(total, soft_aces, rank)
    return total, soft_aces, cards_remaining


def _play_until_17_policy(
    total: int,
    soft_aces: int,
    deck_counts: list[int],
    cards_remaining: int,
    rng: random.Random,
) -> tuple[int, int, int]:
    while not is_bust(total) and total < 17:
        rank, cards_remaining = _draw_rank(deck_counts, cards_remaining, rng)
        total, soft_aces = _add_card_to_total_fast(total, soft_aces, rank)
    return total, soft_aces, cards_remaining


def _play_dealer(
    total: int,
    soft_aces: int,
    deck_counts: list[int],
    cards_remaining: int,
    dealer_hits_soft_17: bool,
    rng: random.Random,
) -> tuple[int, int, int]:
    while total < 17 or (total == 17 and soft_aces > 0 and dealer_hits_soft_17):
        rank, cards_remaining = _draw_rank(deck_counts, cards_remaining, rng)
        total, soft_aces = _add_card_to_total_fast(total, soft_aces, rank)
    return total, soft_aces, cards_remaining


def _compare_totals(player_total: int, dealer_total: int) -> int:
    if is_bust(player_total):
        return -1
    if is_bust(dealer_total):
        return 1
    if player_total > dealer_total:
        return 1
    if player_total < dealer_total:
        return -1
    return 0


def _add_card_to_total_fast(total: int, soft_aces: int, rank: RankIndex) -> tuple[int, int]:
    total += 11 if rank == 0 else CARD_VALUES[rank]
    if rank == 0:
        soft_aces += 1

    while total > 21 and soft_aces:
        total -= 10
        soft_aces -= 1

    return total, soft_aces
