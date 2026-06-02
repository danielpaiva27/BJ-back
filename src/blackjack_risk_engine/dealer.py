from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from blackjack_risk_engine.cards import Card
from blackjack_risk_engine.hand import CardInput, Hand, parse_card
from blackjack_risk_engine.rules import GameRules


class DealerDeck(Protocol):
    def draw(self) -> Card:
        """Draw one card from the deck or shoe."""


@dataclass(frozen=True, slots=True)
class DealerPolicy:
    rules: GameRules

    def should_hit(self, hand: Hand) -> bool:
        if hand.best_value < 17:
            return True
        if hand.best_value == 17 and hand.is_soft and self.rules.dealer_hits_soft_17:
            return True
        return False


@dataclass(frozen=True, slots=True)
class DealerPlayResult:
    final_hand: Hand
    hole_card: Card
    drawn_cards: tuple[Card, ...]

    @property
    def cards(self) -> list[str]:
        return self.final_hand.card_values

    @property
    def total(self) -> int:
        return self.final_hand.total

    @property
    def is_soft(self) -> bool:
        return self.final_hand.is_soft

    @property
    def is_bust(self) -> bool:
        return self.final_hand.is_bust

    @property
    def is_blackjack(self) -> bool:
        return self.final_hand.is_blackjack


def play_dealer_hand(
    up_card: CardInput,
    deck: DealerDeck,
    rules: GameRules | None = None,
) -> DealerPlayResult:
    dealer_up_card = parse_card(up_card)
    hole_card = deck.draw()
    hand = Hand([dealer_up_card, hole_card])

    return play_dealer_hand_from_initial_hand(
        initial_hand=hand,
        hole_card=hole_card,
        deck=deck,
        rules=rules,
    )


def play_dealer_hand_from_initial_hand(
    initial_hand: Hand,
    hole_card: CardInput,
    deck: DealerDeck,
    rules: GameRules | None = None,
) -> DealerPlayResult:
    active_rules = rules or GameRules()
    policy = DealerPolicy(active_rules)
    hand = Hand(initial_hand.cards)
    drawn_cards: list[Card] = []

    while policy.should_hit(hand):
        drawn_card = deck.draw()
        drawn_cards.append(drawn_card)
        hand.add(drawn_card)

    return DealerPlayResult(
        final_hand=hand,
        hole_card=parse_card(hole_card),
        drawn_cards=tuple(drawn_cards),
    )
