from __future__ import annotations

import random
from dataclasses import dataclass, field

from blackjack_risk_engine.cards import Card, Rank, Suit


def standard_deck() -> list[Card]:
    return [Card(rank=rank, suit=suit) for suit in Suit for rank in Rank]


@dataclass(slots=True)
class Shoe:
    deck_count: int = 6
    cards: list[Card] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.deck_count <= 0:
            raise ValueError("deck_count must be greater than zero")
        if not self.cards:
            self.cards = standard_deck() * self.deck_count

    def shuffle(self, rng: random.Random | None = None) -> None:
        (rng or random).shuffle(self.cards)

    def draw(self) -> Card:
        if not self.cards:
            raise IndexError("cannot draw from an empty shoe")
        return self.cards.pop()

    def remaining(self) -> int:
        return len(self.cards)

    def decks_remaining(self) -> float:
        return self.remaining() / 52
