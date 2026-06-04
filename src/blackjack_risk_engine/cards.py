from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from blackjack_risk_engine.engine_core.cards import card_value, string_to_rank


class Rank(str, Enum):
    ACE = "A"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"

    @property
    def hard_value(self) -> int:
        return card_value(string_to_rank(self.value))


@dataclass(frozen=True, slots=True)
class Card:
    rank: Rank

    @property
    def value(self) -> int:
        return self.rank.hard_value

    def __str__(self) -> str:
        return self.rank.value
