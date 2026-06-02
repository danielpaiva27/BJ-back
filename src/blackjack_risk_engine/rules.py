from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TableRules:
    deck_count: int = 6
    dealer_hits_soft_17: bool = False
    blackjack_payout: float = 1.5
    double_after_split_allowed: bool = True
    surrender_allowed: bool = False
    max_split_hands: int = 4

    def __post_init__(self) -> None:
        if self.deck_count <= 0:
            raise ValueError("deck_count must be greater than zero")
        if self.blackjack_payout <= 0:
            raise ValueError("blackjack_payout must be greater than zero")
        if self.max_split_hands < 1:
            raise ValueError("max_split_hands must be at least one")
