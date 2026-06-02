from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Iterable

from blackjack_risk_engine.cards import Card, Rank


CardInput = Card | Rank | str


def parse_card(card: CardInput) -> Card:
    if isinstance(card, Card):
        return card
    if isinstance(card, Rank):
        return Card(card)
    try:
        return Card(Rank(card))
    except ValueError as error:
        allowed = ", ".join(rank.value for rank in Rank)
        raise ValueError(f"invalid blackjack card {card!r}; expected one of: {allowed}") from error


def parse_cards(cards: Iterable[CardInput]) -> list[Card]:
    return [parse_card(card) for card in cards]


@dataclass(slots=True)
class Hand:
    cards: list[Card] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cards = parse_cards(self.cards)

    @classmethod
    def from_values(cls, cards: Iterable[CardInput]) -> Hand:
        return cls(parse_cards(cards))

    def add(self, card: CardInput) -> None:
        self.cards.append(parse_card(card))

    @property
    def values(self) -> set[int]:
        total = sum(card.value for card in self.cards)
        ace_count = sum(1 for card in self.cards if card.rank is Rank.ACE)
        totals = {total}

        for soft_aces in range(1, ace_count + 1):
            totals.add(total + 10 * soft_aces)

        return totals

    @property
    def total(self) -> int:
        non_bust_values = [value for value in self.values if value <= 21]
        if non_bust_values:
            return max(non_bust_values)
        return min(self.values)

    @property
    def best_value(self) -> int:
        return self.total

    @property
    def is_blackjack(self) -> bool:
        return len(self.cards) == 2 and self.total == 21

    @property
    def is_bust(self) -> bool:
        return self.total > 21

    @property
    def is_soft(self) -> bool:
        hard_total = sum(card.value for card in self.cards)
        return any(value <= 21 and value != hard_total for value in self.values)

    @property
    def is_pair(self) -> bool:
        return len(self.cards) == 2 and self.cards[0].rank is self.cards[1].rank

    @property
    def can_split(self) -> bool:
        return self.is_pair

    @property
    def card_values(self) -> list[str]:
        return [card.rank.value for card in self.cards]

    def __str__(self) -> str:
        return " ".join(str(card) for card in self.cards) or "<empty>"
