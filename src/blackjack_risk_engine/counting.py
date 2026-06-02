from __future__ import annotations

from collections.abc import Iterable

from blackjack_risk_engine.cards import Card, Rank


LOW_CARDS = {Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX}
HIGH_CARDS = {Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE}


def hi_lo_value(card: Card) -> int:
    if card.rank in LOW_CARDS:
        return 1
    if card.rank in HIGH_CARDS:
        return -1
    return 0


def running_count(cards: Iterable[Card]) -> int:
    return sum(hi_lo_value(card) for card in cards)


def true_count(count: int, decks_remaining: float) -> float:
    if decks_remaining <= 0:
        raise ValueError("decks_remaining must be greater than zero")
    return count / decks_remaining
