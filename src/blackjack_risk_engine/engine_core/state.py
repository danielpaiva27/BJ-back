from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from blackjack_risk_engine.engine_core.cards import (
    RankIndex,
    deck_counts_after_removal,
    remaining_ordered_deck_ranks,
)
from blackjack_risk_engine.engine_core.rules import CoreRules


@dataclass(frozen=True, slots=True)
class CoreGameState:
    player_ranks: tuple[RankIndex, ...]
    dealer_upcard_rank: RankIndex
    seen_ranks: tuple[RankIndex, ...]
    deck_counts: tuple[int, ...]
    rules: CoreRules

    @property
    def removed_ranks(self) -> tuple[RankIndex, ...]:
        return (*self.seen_ranks, *self.player_ranks, self.dealer_upcard_rank)

    @property
    def cards_remaining(self) -> int:
        return sum(self.deck_counts)


def build_core_state(
    player_ranks: Iterable[RankIndex],
    dealer_upcard_rank: RankIndex,
    seen_ranks: Iterable[RankIndex],
    rules: CoreRules | None = None,
) -> CoreGameState:
    active_rules = rules or CoreRules()
    player_tuple = tuple(player_ranks)
    seen_tuple = tuple(seen_ranks)
    removed_ranks = (*seen_tuple, *player_tuple, dealer_upcard_rank)
    deck_counts = deck_counts_after_removal(active_rules.number_of_decks, removed_ranks)

    return CoreGameState(
        player_ranks=player_tuple,
        dealer_upcard_rank=dealer_upcard_rank,
        seen_ranks=seen_tuple,
        deck_counts=deck_counts,
        rules=active_rules,
    )


def remaining_ordered_ranks_for_state(state: CoreGameState) -> tuple[RankIndex, ...]:
    return remaining_ordered_deck_ranks(state.rules.number_of_decks, state.removed_ranks)
