from __future__ import annotations

from blackjack_risk_engine.cards import Card
from blackjack_risk_engine.decisions import Decision, get_legal_actions
from blackjack_risk_engine.hand import Hand
from blackjack_risk_engine.rules import GameRules


def recommend_basic_strategy(hand: Hand, dealer_up_card: Card, rules: GameRules | None = None) -> Decision:
    """Recommend an initial action using a simplified, configurable strategy.

    This is a compact approximation of common blackjack basic strategy. It
    covers hard totals, soft totals, and pairs, while respecting the currently
    legal actions from the provided table rules.
    """

    active_rules = rules or GameRules()
    legal_actions = get_legal_actions(hand, active_rules)
    dealer_value = _dealer_strategy_value(dealer_up_card)

    if hand.can_split:
        action = _choose_pair_action(hand, dealer_value)
    elif hand.is_soft:
        action = _choose_initial_soft_action(hand.total, dealer_value)
    else:
        action = _choose_initial_hard_action(hand.total, dealer_value, legal_actions)

    return action if action in legal_actions else _fallback_legal_action(action, legal_actions)


def choose_continuation_action(hand: Hand, dealer_up_card: Card) -> Decision:
    """Choose hit/stand using a simplified basic-strategy continuation policy.

    This is intentionally not recursive EV search. It considers hard/soft total
    plus the dealer up card and returns only hit or stand for an in-progress hand.
    """

    if hand.is_bust:
        return Decision.STAND

    dealer_value = _dealer_strategy_value(dealer_up_card)

    if hand.is_soft:
        return _choose_soft_action(hand.total, dealer_value)

    return _choose_hard_action(hand.total, dealer_value)


def _choose_hard_action(total: int, dealer_value: int) -> Decision:
    if total <= 11:
        return Decision.HIT
    if total == 12:
        return Decision.STAND if 4 <= dealer_value <= 6 else Decision.HIT
    if 13 <= total <= 16:
        return Decision.STAND if 2 <= dealer_value <= 6 else Decision.HIT
    return Decision.STAND


def _choose_soft_action(total: int, dealer_value: int) -> Decision:
    if total <= 17:
        return Decision.HIT
    if total == 18:
        return Decision.STAND if 2 <= dealer_value <= 8 else Decision.HIT
    return Decision.STAND


def _dealer_strategy_value(dealer_up_card: Card) -> int:
    return 11 if dealer_up_card.rank.value == "A" else dealer_up_card.value


def _choose_initial_hard_action(
    total: int,
    dealer_value: int,
    legal_actions: tuple[Decision, ...],
) -> Decision:
    if total <= 8:
        return Decision.HIT
    if total == 9:
        return Decision.DOUBLE if 3 <= dealer_value <= 6 and Decision.DOUBLE in legal_actions else Decision.HIT
    if total == 10:
        return Decision.DOUBLE if 2 <= dealer_value <= 9 and Decision.DOUBLE in legal_actions else Decision.HIT
    if total == 11:
        return Decision.DOUBLE if dealer_value <= 10 and Decision.DOUBLE in legal_actions else Decision.HIT
    if total == 12:
        return Decision.STAND if 4 <= dealer_value <= 6 else Decision.HIT
    if 13 <= total <= 15:
        return Decision.STAND if 2 <= dealer_value <= 6 else Decision.HIT
    if total == 16:
        if dealer_value >= 9 and Decision.SURRENDER in legal_actions:
            return Decision.SURRENDER
        return Decision.STAND if 2 <= dealer_value <= 6 else Decision.HIT
    return Decision.STAND


def _choose_initial_soft_action(total: int, dealer_value: int) -> Decision:
    if total <= 14:
        return Decision.DOUBLE if 5 <= dealer_value <= 6 else Decision.HIT
    if 15 <= total <= 16:
        return Decision.DOUBLE if 4 <= dealer_value <= 6 else Decision.HIT
    if total == 17:
        return Decision.DOUBLE if 3 <= dealer_value <= 6 else Decision.HIT
    if total == 18:
        if 3 <= dealer_value <= 6:
            return Decision.DOUBLE
        return Decision.STAND if 2 <= dealer_value <= 8 else Decision.HIT
    return Decision.STAND


def _choose_pair_action(hand: Hand, dealer_value: int) -> Decision:
    rank = hand.cards[0].rank.value

    if rank in {"A", "8"}:
        return Decision.SPLIT
    if rank == "10":
        return Decision.STAND
    if rank == "9":
        return Decision.SPLIT if dealer_value in {2, 3, 4, 5, 6, 8, 9} else Decision.STAND
    if rank == "7":
        return Decision.SPLIT if 2 <= dealer_value <= 7 else Decision.HIT
    if rank == "6":
        return Decision.SPLIT if 2 <= dealer_value <= 6 else Decision.HIT
    if rank == "5":
        return Decision.DOUBLE if 2 <= dealer_value <= 9 else Decision.HIT
    if rank == "4":
        return Decision.SPLIT if 5 <= dealer_value <= 6 else Decision.HIT
    if rank in {"2", "3"}:
        return Decision.SPLIT if 2 <= dealer_value <= 7 else Decision.HIT
    return Decision.HIT


def _fallback_legal_action(preferred_action: Decision, legal_actions: tuple[Decision, ...]) -> Decision:
    if preferred_action is Decision.DOUBLE:
        return Decision.HIT
    if preferred_action is Decision.SPLIT:
        return Decision.HIT
    if preferred_action is Decision.SURRENDER:
        return Decision.HIT
    return legal_actions[0]
