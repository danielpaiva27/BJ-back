from __future__ import annotations

from collections.abc import Iterable

from blackjack_risk_engine.cards import Card, Rank
from blackjack_risk_engine.engine_core.cards import (
    RankIndex,
    rank_to_string,
    string_to_rank,
)
from blackjack_risk_engine.engine_core.hand import evaluate_hand_from_ranks
from blackjack_risk_engine.engine_core.rules import CoreRules
from blackjack_risk_engine.engine_core.state import CoreGameState, build_core_state
from blackjack_risk_engine.rules import GameRules


def card_input_to_rank(card: object) -> RankIndex:
    if isinstance(card, Card):
        return string_to_rank(card.rank.value)
    if isinstance(card, Rank):
        return string_to_rank(card.value)
    if isinstance(card, str):
        return string_to_rank(card)

    allowed = ", ".join(rank_to_string(rank) for rank in range(10))
    raise ValueError(f"invalid blackjack card {card!r}; expected one of: {allowed}")


def cards_to_ranks(cards: Iterable[object]) -> tuple[RankIndex, ...]:
    return tuple(card_input_to_rank(card) for card in cards)


def rank_to_card(rank: RankIndex) -> Card:
    return Card(Rank(rank_to_string(rank)))


def ranks_to_cards(ranks: Iterable[RankIndex]) -> list[Card]:
    return [rank_to_card(rank) for rank in ranks]


def ranks_to_strings(ranks: Iterable[RankIndex]) -> list[str]:
    return [rank_to_string(rank) for rank in ranks]


def game_rules_to_core_rules(rules: GameRules | CoreRules | None = None) -> CoreRules:
    if rules is None:
        return CoreRules()
    if isinstance(rules, CoreRules):
        return rules

    return CoreRules(
        number_of_decks=rules.number_of_decks,
        dealer_hits_soft_17=rules.dealer_hits_soft_17,
        blackjack_payout=rules.blackjack_payout,
        double_allowed=rules.double_allowed,
        double_after_split=rules.double_after_split,
        surrender_allowed=rules.surrender_allowed,
        max_splits=rules.max_splits,
        dealer_peek=rules.dealer_peek,
        hit_split_aces=rules.hit_split_aces,
        resplit_aces=rules.resplit_aces,
    )


def core_rules_to_game_rules(rules: CoreRules | GameRules | None = None) -> GameRules:
    if rules is None:
        return GameRules()
    if isinstance(rules, GameRules):
        return rules

    return GameRules(
        number_of_decks=rules.number_of_decks,
        dealer_hits_soft_17=rules.dealer_hits_soft_17,
        blackjack_payout=rules.blackjack_payout,
        double_allowed=rules.double_allowed,
        double_after_split=rules.double_after_split,
        surrender_allowed=rules.surrender_allowed,
        max_splits=rules.max_splits,
        dealer_peek=rules.dealer_peek,
        hit_split_aces=rules.hit_split_aces,
        resplit_aces=rules.resplit_aces,
    )


def build_core_state_from_inputs(
    player_hand: object,
    dealer_up_card: object,
    seen_cards: Iterable[object],
    rules: GameRules | CoreRules | None = None,
) -> CoreGameState:
    core_rules = game_rules_to_core_rules(rules)
    player_ranks = _hand_to_ranks(player_hand)
    dealer_rank = card_input_to_rank(dealer_up_card)
    seen_ranks = cards_to_ranks(seen_cards)
    return build_core_state(
        player_ranks=player_ranks,
        dealer_upcard_rank=dealer_rank,
        seen_ranks=seen_ranks,
        rules=core_rules,
    )


def core_rules_to_public_dict(rules: CoreRules | GameRules) -> dict:
    core_rules = game_rules_to_core_rules(rules)
    return {
        "number_of_decks": core_rules.number_of_decks,
        "dealer_hits_soft_17": core_rules.dealer_hits_soft_17,
        "blackjack_payout": core_rules.blackjack_payout,
        "blackjack_payout_multiplier": core_rules.blackjack_payout_multiplier,
        "double_allowed": core_rules.double_allowed,
        "double_after_split": core_rules.double_after_split,
        "surrender_allowed": core_rules.surrender_allowed,
        "max_splits": core_rules.max_splits,
        "dealer_peek": core_rules.dealer_peek,
        "hit_split_aces": core_rules.hit_split_aces,
        "resplit_aces": core_rules.resplit_aces,
    }


def core_state_to_public_input(state: CoreGameState) -> dict:
    return {
        "player": ranks_to_strings(state.player_ranks),
        "dealer": rank_to_string(state.dealer_upcard_rank),
        "seen": ranks_to_strings(state.seen_ranks),
    }


def core_state_to_public_hand_analysis(state: CoreGameState) -> dict:
    evaluation = evaluate_hand_from_ranks(state.player_ranks)
    return {
        "cards": ranks_to_strings(state.player_ranks),
        "total": evaluation.total,
        "is_soft": evaluation.is_soft,
        "is_bust": evaluation.is_bust,
        "is_blackjack": evaluation.is_blackjack,
        "is_pair": evaluation.is_pair,
        "can_split": evaluation.can_split,
    }


def build_analyze_hand_response(
    *,
    state: CoreGameState,
    actions: list[dict],
    recommendation: dict,
    count_analysis: object,
    betting: object,
    metadata: dict,
) -> dict:
    return {
        "input": core_state_to_public_input(state),
        "rules": core_rules_to_public_dict(state.rules),
        "hand_analysis": core_state_to_public_hand_analysis(state),
        "counting": {
            "running_count": count_analysis.running_count,
            "true_count": count_analysis.true_count,
            "cards_remaining": count_analysis.cards_remaining,
            "deck_status": count_analysis.deck_status,
        },
        "actions": actions,
        "recommendation": recommendation,
        "betting": {
            "suggested_bet": betting.suggested_bet,
            "bet_units": betting.bet_units,
            "risk_profile": betting.risk_profile,
            "explanation": betting.explanation,
        },
        "metadata": metadata,
    }


def _hand_to_ranks(player_hand: object) -> tuple[RankIndex, ...]:
    rank_indices = getattr(player_hand, "rank_indices", None)
    if rank_indices is not None:
        return tuple(rank_indices)
    return cards_to_ranks(player_hand)
