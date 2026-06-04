from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from blackjack_risk_engine.cards import Card
from blackjack_risk_engine.deck import Shoe
from blackjack_risk_engine.engine_core.cards import hi_lo_weight, string_to_rank
from blackjack_risk_engine.hand import CardInput, parse_cards
from blackjack_risk_engine.rules import GameRules


@dataclass(frozen=True, slots=True)
class CountAnalysis:
    running_count: int
    true_count: float
    cards_remaining: int
    deck_status: str


def hi_lo_value(card: Card) -> int:
    return hi_lo_weight(string_to_rank(card.rank.value))


def running_count(cards: Iterable[Card]) -> int:
    return sum(hi_lo_value(card) for card in cards)


def true_count(count: int, cards_remaining: int | None = None, decks_remaining: float | None = None) -> float:
    if decks_remaining is None:
        if cards_remaining is None:
            raise ValueError("cards_remaining or decks_remaining must be provided")
        decks_remaining = cards_remaining / 52

    if decks_remaining <= 0:
        return 0.0
    return count / decks_remaining


def deck_status(count: float) -> str:
    if count <= -3:
        return "muito desfavor\u00e1vel"
    if count < -1:
        return "desfavor\u00e1vel"
    if count <= 1:
        return "neutro"
    if count < 3:
        return "favor\u00e1vel"
    return "muito favor\u00e1vel"


def analyze_count(
    known_cards: Iterable[CardInput],
    rules: GameRules | None = None,
) -> CountAnalysis:
    active_rules = rules or GameRules()
    cards = parse_cards(known_cards)
    shoe = Shoe(deck_count=active_rules.number_of_decks)
    shoe.remove_seen_cards(cards)

    count = running_count(cards)
    remaining = shoe.remaining()
    adjusted_count = true_count(count, cards_remaining=remaining)

    return CountAnalysis(
        running_count=count,
        true_count=adjusted_count,
        cards_remaining=remaining,
        deck_status=deck_status(adjusted_count),
    )
