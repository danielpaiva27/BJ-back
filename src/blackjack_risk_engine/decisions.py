from enum import Enum

from blackjack_risk_engine.hand import Hand
from blackjack_risk_engine.rules import GameRules


class Decision(str, Enum):
    HIT = "hit"
    STAND = "stand"
    DOUBLE = "double"
    SPLIT = "split"
    SURRENDER = "surrender"


def get_legal_actions(hand: Hand, rules: GameRules, splits_done: int = 0) -> tuple[Decision, ...]:
    if hand.is_blackjack:
        return (Decision.STAND,)

    actions = [Decision.HIT, Decision.STAND]

    if rules.double_allowed and len(hand.cards) == 2:
        actions.append(Decision.DOUBLE)

    if rules.surrender_allowed and len(hand.cards) == 2:
        actions.append(Decision.SURRENDER)

    if hand.can_split and splits_done < rules.max_splits:
        actions.append(Decision.SPLIT)

    return tuple(actions)
