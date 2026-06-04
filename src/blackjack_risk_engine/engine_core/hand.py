from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from blackjack_risk_engine.engine_core.cards import RankIndex, card_value


@dataclass(frozen=True, slots=True)
class HandEvaluation:
    ranks: tuple[RankIndex, ...]
    hard_total: int
    values: frozenset[int]
    total: int
    soft_aces: int

    @property
    def is_soft(self) -> bool:
        return self.soft_aces > 0

    @property
    def is_bust(self) -> bool:
        return is_bust(self.total)

    @property
    def is_blackjack(self) -> bool:
        return len(self.ranks) == 2 and self.total == 21

    @property
    def is_pair(self) -> bool:
        return len(self.ranks) == 2 and self.ranks[0] == self.ranks[1]

    @property
    def can_split(self) -> bool:
        return self.is_pair


def evaluate_hand_from_ranks(ranks: Iterable[RankIndex]) -> HandEvaluation:
    rank_tuple = tuple(ranks)
    total = 0
    soft_aces = 0

    for rank in rank_tuple:
        total, soft_aces = add_card_to_total(total, soft_aces, rank)

    values = hand_values_from_ranks(rank_tuple)
    hard_total = min(values) if values else 0
    return HandEvaluation(
        ranks=rank_tuple,
        hard_total=hard_total,
        values=frozenset(values),
        total=total,
        soft_aces=soft_aces,
    )


def add_card_to_total(total: int, soft_aces: int, rank: RankIndex) -> tuple[int, int]:
    total += 11 if rank == 0 else card_value(rank)
    if rank == 0:
        soft_aces += 1

    while total > 21 and soft_aces:
        total -= 10
        soft_aces -= 1

    return total, soft_aces


def hand_values_from_ranks(ranks: Iterable[RankIndex]) -> frozenset[int]:
    rank_tuple = tuple(ranks)
    hard_total = sum(card_value(rank) for rank in rank_tuple)
    ace_count = sum(1 for rank in rank_tuple if rank == 0)
    values = {hard_total}

    for soft_aces in range(1, ace_count + 1):
        values.add(hard_total + 10 * soft_aces)

    return frozenset(values)


def is_blackjack_two_cards(ranks: Iterable[RankIndex]) -> bool:
    rank_tuple = tuple(ranks)
    return len(rank_tuple) == 2 and evaluate_hand_from_ranks(rank_tuple).total == 21


def is_bust(total: int) -> bool:
    return total > 21


def hand_total_display(ranks: Iterable[RankIndex]) -> int:
    return evaluate_hand_from_ranks(ranks).total
