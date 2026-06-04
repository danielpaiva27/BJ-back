from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Iterable

from blackjack_risk_engine.cards import Card, Rank
from blackjack_risk_engine.engine_core.cards import rank_to_string
from blackjack_risk_engine.engine_core.adapters import card_input_to_rank, rank_to_card
from blackjack_risk_engine.engine_core.hand import add_card_to_total, hand_values_from_ranks


CardInput = Card | Rank | str


def parse_card(card: CardInput) -> Card:
    return rank_to_card(card_input_to_rank(card))


def parse_cards(cards: Iterable[CardInput]) -> list[Card]:
    return [parse_card(card) for card in cards]


@dataclass(slots=True)
class Hand:
    cards: list[Card] = field(default_factory=list)
    _rank_indices: list[int] = field(default_factory=list, init=False, repr=False)
    _total: int = field(default=0, init=False, repr=False)
    _soft_aces: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self.cards = parse_cards(self.cards)
        self._rank_indices = []
        self._total = 0
        self._soft_aces = 0
        for card in self.cards:
            rank = card_input_to_rank(card)
            self._rank_indices.append(rank)
            self._total, self._soft_aces = add_card_to_total(self._total, self._soft_aces, rank)

    @classmethod
    def from_values(cls, cards: Iterable[CardInput]) -> Hand:
        return cls(cards)

    def add(self, card: CardInput) -> None:
        parsed_card = parse_card(card)
        rank = card_input_to_rank(parsed_card)
        self.cards.append(parsed_card)
        self._rank_indices.append(rank)
        self._total, self._soft_aces = add_card_to_total(self._total, self._soft_aces, rank)

    @property
    def rank_indices(self) -> tuple[int, ...]:
        return tuple(self._rank_indices)

    @property
    def values(self) -> set[int]:
        return set(hand_values_from_ranks(self._rank_indices))

    @property
    def total(self) -> int:
        return self._total

    @property
    def best_value(self) -> int:
        return self.total

    @property
    def is_blackjack(self) -> bool:
        return len(self._rank_indices) == 2 and self._total == 21

    @property
    def is_bust(self) -> bool:
        return self._total > 21

    @property
    def is_soft(self) -> bool:
        return self._soft_aces > 0

    @property
    def is_pair(self) -> bool:
        return len(self._rank_indices) == 2 and self._rank_indices[0] == self._rank_indices[1]

    @property
    def can_split(self) -> bool:
        return self.is_pair

    @property
    def card_values(self) -> list[str]:
        return [rank_to_string(rank) for rank in self._rank_indices]

    def __str__(self) -> str:
        return " ".join(str(card) for card in self.cards) or "<empty>"
