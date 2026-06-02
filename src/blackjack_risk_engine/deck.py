from __future__ import annotations

import random
from dataclasses import dataclass, field
from collections.abc import Iterable

from blackjack_risk_engine.cards import Card, Rank


def standard_deck() -> list[Card]:
    cards: list[Card] = []
    cards.extend(Card(Rank.ACE) for _ in range(4))

    for rank in (
        Rank.TWO,
        Rank.THREE,
        Rank.FOUR,
        Rank.FIVE,
        Rank.SIX,
        Rank.SEVEN,
        Rank.EIGHT,
        Rank.NINE,
    ):
        cards.extend(Card(rank) for _ in range(4))

    cards.extend(Card(Rank.TEN) for _ in range(16))
    return cards


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

    def draw(self, rng: random.Random | None = None) -> Card:
        if not self.cards:
            raise IndexError("cannot draw from an empty shoe")
        random_source = rng or random
        index = random_source.randrange(len(self.cards))
        return self.cards.pop(index)

    def remove_card(self, card: Card) -> None:
        try:
            self.cards.remove(card)
        except ValueError as error:
            raise ValueError(f"cannot remove card {card}: not present in shoe") from error

    def remove_seen_cards(self, seen_cards: Iterable[Card]) -> None:
        for card in seen_cards:
            self.remove_card(card)

    def remaining(self) -> int:
        return len(self.cards)

    def decks_remaining(self) -> float:
        return self.remaining() / 52
