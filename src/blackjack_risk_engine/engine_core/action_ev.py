from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable, NamedTuple

from blackjack_risk_engine.engine_core.cards import RANK_STRINGS, RankIndex
from blackjack_risk_engine.engine_core.dealer_dp import (
    dealer_outcome_distribution,
    natural_blackjack_stand_ev,
    stand_ev_from_distribution,
)
from blackjack_risk_engine.engine_core.hand import add_card_to_total, evaluate_hand_from_ranks
from blackjack_risk_engine.engine_core.rules import CoreRules
from blackjack_risk_engine.engine_core.state import CoreGameState


DETERMINISTIC_ACTIONS = {"hit", "stand", "double", "surrender"}


class DeterministicEvCacheLimitExceeded(RuntimeError):
    pass


class OutcomeStats(NamedTuple):
    expected_value: float
    win_rate: float
    lose_rate: float
    push_rate: float
    second_moment: float

    @property
    def std_dev(self) -> float:
        variance = max(0.0, self.second_moment - self.expected_value * self.expected_value)
        return sqrt(variance)


@dataclass(frozen=True, slots=True)
class ActionEvResult:
    action: str
    ev: float
    win_rate: float
    lose_rate: float
    push_rate: float
    std_dev: float
    method: str = "deterministic_dp"


@dataclass(frozen=True, slots=True)
class ActionEvRanking:
    actions: tuple[ActionEvResult, ...]
    unsupported_actions: tuple[str, ...]
    cache_states: int
    method: str


class ActionEvCalculator:
    def __init__(self, rules: CoreRules, max_cache_states: int = 200_000) -> None:
        if max_cache_states <= 0:
            raise ValueError("max_cache_states must be greater than zero")
        self.rules = rules
        self.max_cache_states = max_cache_states
        self._hit_cache: dict[tuple[int, int, int, tuple[int, ...]], OutcomeStats] = {}
        self._best_cache: dict[tuple[int, int, int, tuple[int, ...]], OutcomeStats] = {}
        self._stand_cache: dict[tuple[int, int, tuple[int, ...]], OutcomeStats] = {}

    @property
    def cache_states(self) -> int:
        return len(self._hit_cache) + len(self._best_cache) + len(self._stand_cache)

    def ev_stand(
        self,
        player_total: int,
        dealer_upcard_rank: RankIndex,
        deck_counts: tuple[int, ...],
    ) -> OutcomeStats:
        key = (player_total, dealer_upcard_rank, tuple(deck_counts))
        cached = self._stand_cache.get(key)
        if cached is not None:
            return cached

        self._ensure_cache_budget()
        result = ev_stand(player_total, dealer_upcard_rank, deck_counts, self.rules)
        self._stand_cache[key] = result
        return result

    def ev_hit(
        self,
        player_total: int,
        soft_aces: int,
        dealer_upcard_rank: RankIndex,
        deck_counts: tuple[int, ...],
    ) -> OutcomeStats:
        key = (player_total, soft_aces, dealer_upcard_rank, tuple(deck_counts))
        cached = self._hit_cache.get(key)
        if cached is not None:
            return cached

        self._ensure_cache_budget()
        counts = _validate_deck_counts(deck_counts)
        remaining_cards = sum(counts)
        if remaining_cards <= 0:
            return self.ev_stand(player_total, dealer_upcard_rank, counts)

        weighted = _zero_stats()
        for rank, count in enumerate(counts):
            if count <= 0:
                continue

            next_counts = _remove_rank(counts, rank)
            next_total, next_soft_aces = add_card_to_total(player_total, soft_aces, rank)
            if next_total > 21:
                branch = _constant_loss(-1.0)
            else:
                branch = self.best_hit_stand(next_total, next_soft_aces, dealer_upcard_rank, next_counts)

            weighted = _add_weighted_stats(weighted, branch, count / remaining_cards)

        self._hit_cache[key] = weighted
        return weighted

    def ev_double(
        self,
        player_total: int,
        soft_aces: int,
        dealer_upcard_rank: RankIndex,
        deck_counts: tuple[int, ...],
    ) -> OutcomeStats:
        if not self.rules.double_allowed:
            raise ValueError("double is not allowed by the current rules")

        counts = _validate_deck_counts(deck_counts)
        remaining_cards = sum(counts)
        if remaining_cards <= 0:
            raise ValueError("deck_counts must contain at least one card for double")

        weighted = _zero_stats()
        for rank, count in enumerate(counts):
            if count <= 0:
                continue

            next_counts = _remove_rank(counts, rank)
            next_total, _next_soft_aces = add_card_to_total(player_total, soft_aces, rank)
            if next_total > 21:
                branch = _constant_loss(-2.0)
            else:
                branch = _multiply_outcomes(
                    self.ev_stand(next_total, dealer_upcard_rank, next_counts),
                    2.0,
                )

            weighted = _add_weighted_stats(weighted, branch, count / remaining_cards)

        return weighted

    def ev_surrender(self) -> OutcomeStats:
        if not self.rules.surrender_allowed:
            raise ValueError("surrender is not allowed by the current rules")
        return ev_surrender(self.rules)

    def best_hit_stand(
        self,
        player_total: int,
        soft_aces: int,
        dealer_upcard_rank: RankIndex,
        deck_counts: tuple[int, ...],
    ) -> OutcomeStats:
        key = (player_total, soft_aces, dealer_upcard_rank, tuple(deck_counts))
        cached = self._best_cache.get(key)
        if cached is not None:
            return cached

        self._ensure_cache_budget()
        stand = self.ev_stand(player_total, dealer_upcard_rank, deck_counts)
        hit = self.ev_hit(player_total, soft_aces, dealer_upcard_rank, deck_counts)
        best = hit if hit.expected_value > stand.expected_value else stand
        self._best_cache[key] = best
        return best

    def _ensure_cache_budget(self) -> None:
        if self.cache_states >= self.max_cache_states:
            raise DeterministicEvCacheLimitExceeded(
                f"deterministic EV cache exceeded {self.max_cache_states} states"
            )


def ev_stand(
    player_total: int,
    dealer_upcard_rank: RankIndex,
    deck_counts: tuple[int, ...],
    rules: CoreRules,
) -> OutcomeStats:
    if player_total > 21:
        return _constant_loss(-1.0)

    distribution = dealer_outcome_distribution(
        dealer_upcard_rank=dealer_upcard_rank,
        deck_counts=deck_counts,
        dealer_hits_soft_17=rules.dealer_hits_soft_17,
    )
    stand = stand_ev_from_distribution(player_total, distribution)
    return OutcomeStats(
        expected_value=stand.expected_value,
        win_rate=stand.win_rate,
        lose_rate=stand.lose_rate,
        push_rate=stand.push_rate,
        second_moment=stand.win_rate + stand.lose_rate,
    )


def ev_blackjack_stand(
    dealer_upcard_rank: RankIndex,
    deck_counts: tuple[int, ...],
    rules: CoreRules,
) -> OutcomeStats:
    result = natural_blackjack_stand_ev(
        dealer_upcard_rank=dealer_upcard_rank,
        deck_counts=deck_counts,
        blackjack_payout_multiplier=rules.blackjack_payout_multiplier,
    )
    second_moment = result.win_rate * rules.blackjack_payout_multiplier * rules.blackjack_payout_multiplier
    return OutcomeStats(
        expected_value=result.expected_value,
        win_rate=result.win_rate,
        lose_rate=result.lose_rate,
        push_rate=result.push_rate,
        second_moment=second_moment,
    )


def ev_hit(
    player_total: int,
    soft_aces: int,
    dealer_upcard_rank: RankIndex,
    deck_counts: tuple[int, ...],
    rules: CoreRules,
    max_cache_states: int = 200_000,
) -> OutcomeStats:
    return ActionEvCalculator(rules, max_cache_states=max_cache_states).ev_hit(
        player_total,
        soft_aces,
        dealer_upcard_rank,
        deck_counts,
    )


def ev_double(
    player_total: int,
    soft_aces: int,
    dealer_upcard_rank: RankIndex,
    deck_counts: tuple[int, ...],
    rules: CoreRules,
    max_cache_states: int = 200_000,
) -> OutcomeStats:
    return ActionEvCalculator(rules, max_cache_states=max_cache_states).ev_double(
        player_total,
        soft_aces,
        dealer_upcard_rank,
        deck_counts,
    )


def ev_surrender(rules: CoreRules) -> OutcomeStats:
    if not rules.surrender_allowed:
        raise ValueError("surrender is not allowed by the current rules")
    return OutcomeStats(
        expected_value=-0.5,
        win_rate=0.0,
        lose_rate=1.0,
        push_rate=0.0,
        second_moment=0.25,
    )


def calculate_action_evs_deterministic(
    state: CoreGameState,
    legal_actions: Iterable[str],
    max_cache_states: int = 200_000,
) -> ActionEvRanking:
    actions = tuple(legal_actions)
    unsupported = tuple(action for action in actions if action not in DETERMINISTIC_ACTIONS)
    player = evaluate_hand_from_ranks(state.player_ranks)
    calculator = ActionEvCalculator(state.rules, max_cache_states=max_cache_states)

    results: list[ActionEvResult] = []
    for action in actions:
        if action == "stand":
            stats = (
                ev_blackjack_stand(state.dealer_upcard_rank, state.deck_counts, state.rules)
                if player.is_blackjack
                else calculator.ev_stand(player.total, state.dealer_upcard_rank, state.deck_counts)
            )
        elif action == "hit":
            stats = calculator.ev_hit(player.total, player.soft_aces, state.dealer_upcard_rank, state.deck_counts)
        elif action == "double":
            if not state.rules.double_allowed:
                continue
            stats = calculator.ev_double(player.total, player.soft_aces, state.dealer_upcard_rank, state.deck_counts)
        elif action == "surrender":
            if not state.rules.surrender_allowed:
                continue
            stats = calculator.ev_surrender()
        else:
            continue

        results.append(_action_result(action, stats))

    return ActionEvRanking(
        actions=tuple(sorted(results, key=lambda result: result.ev, reverse=True)),
        unsupported_actions=unsupported,
        cache_states=calculator.cache_states,
        method="deterministic_dp",
    )


def _action_result(action: str, stats: OutcomeStats) -> ActionEvResult:
    return ActionEvResult(
        action=action,
        ev=stats.expected_value,
        win_rate=stats.win_rate,
        lose_rate=stats.lose_rate,
        push_rate=stats.push_rate,
        std_dev=stats.std_dev,
    )


def _validate_deck_counts(deck_counts: tuple[int, ...]) -> tuple[int, ...]:
    counts = tuple(deck_counts)
    if len(counts) != len(RANK_STRINGS):
        raise ValueError("deck_counts must contain exactly 10 ranks")
    if any(not isinstance(count, int) for count in counts):
        raise ValueError("deck_counts must contain integer counts")
    if any(count < 0 for count in counts):
        raise ValueError("deck_counts cannot contain negative values")
    return counts


def _remove_rank(deck_counts: tuple[int, ...], rank: RankIndex) -> tuple[int, ...]:
    counts = list(deck_counts)
    counts[rank] -= 1
    return tuple(counts)


def _zero_stats() -> OutcomeStats:
    return OutcomeStats(0.0, 0.0, 0.0, 0.0, 0.0)


def _constant_loss(outcome: float) -> OutcomeStats:
    return OutcomeStats(
        expected_value=outcome,
        win_rate=0.0,
        lose_rate=1.0,
        push_rate=0.0,
        second_moment=outcome * outcome,
    )


def _multiply_outcomes(stats: OutcomeStats, multiplier: float) -> OutcomeStats:
    return OutcomeStats(
        expected_value=stats.expected_value * multiplier,
        win_rate=stats.win_rate,
        lose_rate=stats.lose_rate,
        push_rate=stats.push_rate,
        second_moment=stats.second_moment * multiplier * multiplier,
    )


def _add_weighted_stats(base: OutcomeStats, branch: OutcomeStats, weight: float) -> OutcomeStats:
    return OutcomeStats(
        expected_value=base.expected_value + branch.expected_value * weight,
        win_rate=base.win_rate + branch.win_rate * weight,
        lose_rate=base.lose_rate + branch.lose_rate * weight,
        push_rate=base.push_rate + branch.push_rate * weight,
        second_moment=base.second_moment + branch.second_moment * weight,
    )
