from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class GameRules:
    number_of_decks: int = 6
    dealer_hits_soft_17: bool = False
    blackjack_payout: Literal["3:2", "6:5"] = "3:2"
    double_allowed: bool = True
    double_after_split: bool = True
    surrender_allowed: bool = False
    max_splits: int = 3
    dealer_peek: bool = True
    hit_split_aces: bool = False
    resplit_aces: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.number_of_decks, int) or self.number_of_decks <= 0:
            raise ValueError("number_of_decks must be a positive integer")
        if self.blackjack_payout not in {"3:2", "6:5"}:
            raise ValueError("blackjack_payout must be one of: 3:2, 6:5")
        if not isinstance(self.max_splits, int) or self.max_splits < 0:
            raise ValueError("max_splits must be a non-negative integer")

        for field_name in (
            "dealer_hits_soft_17",
            "double_allowed",
            "double_after_split",
            "surrender_allowed",
            "dealer_peek",
            "hit_split_aces",
            "resplit_aces",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")

        if self.resplit_aces and self.max_splits == 0:
            raise ValueError("resplit_aces requires max_splits to be greater than zero")

    @property
    def blackjack_payout_multiplier(self) -> float:
        if self.blackjack_payout == "3:2":
            return 1.5
        return 1.2

    @property
    def deck_count(self) -> int:
        return self.number_of_decks

    @property
    def double_after_split_allowed(self) -> bool:
        return self.double_after_split

    @property
    def max_split_hands(self) -> int:
        return self.max_splits + 1


TableRules = GameRules
