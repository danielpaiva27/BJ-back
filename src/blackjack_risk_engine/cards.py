from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Suit(str, Enum):
    CLUBS = "clubs"
    DIAMONDS = "diamonds"
    HEARTS = "hearts"
    SPADES = "spades"


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
    JACK = "J"
    QUEEN = "Q"
    KING = "K"

    @property
    def hard_value(self) -> int:
        if self is Rank.ACE:
            return 1
        if self in {Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING}:
            return 10
        return int(self.value)


@dataclass(frozen=True, slots=True)
class Card:
    rank: Rank
    suit: Suit

    @property
    def value(self) -> int:
        return self.rank.hard_value

    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.value[0].upper()}"
