from __future__ import annotations

from dataclasses import dataclass

from blackjack_risk_engine.hand import Hand
from blackjack_risk_engine.rules import TableRules


@dataclass(frozen=True, slots=True)
class DealerPolicy:
    rules: TableRules

    def should_hit(self, hand: Hand) -> bool:
        if hand.best_value < 17:
            return True
        if hand.best_value == 17 and hand.is_soft and self.rules.dealer_hits_soft_17:
            return True
        return False
