from __future__ import annotations

from dataclasses import dataclass, field

from blackjack_risk_engine.cards import Card, Rank


@dataclass(slots=True)
class Hand:
    cards: list[Card] = field(default_factory=list)

    def add(self, card: Card) -> None:
        self.cards.append(card)

    @property
    def values(self) -> set[int]:
        total = sum(card.value for card in self.cards)
        ace_count = sum(1 for card in self.cards if card.rank is Rank.ACE)
        totals = {total}

        for soft_aces in range(1, ace_count + 1):
            totals.add(total + 10 * soft_aces)

        return totals

    @property
    def best_value(self) -> int:
        non_bust_values = [value for value in self.values if value <= 21]
        if non_bust_values:
            return max(non_bust_values)
        return min(self.values)

    @property
    def is_blackjack(self) -> bool:
        return len(self.cards) == 2 and self.best_value == 21

    @property
    def is_bust(self) -> bool:
        return self.best_value > 21

    @property
    def is_soft(self) -> bool:
        return any(value <= 21 and value != sum(card.value for card in self.cards) for value in self.values)

    def __str__(self) -> str:
        return " ".join(str(card) for card in self.cards) or "<empty>"
