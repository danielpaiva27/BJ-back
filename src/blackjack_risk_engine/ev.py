from __future__ import annotations

import random
import time
from math import sqrt
from dataclasses import dataclass
from collections.abc import Iterable

from blackjack_risk_engine import __version__
from blackjack_risk_engine.cards import Card
from blackjack_risk_engine.counting import analyze_count
from blackjack_risk_engine.deck import Shoe
from blackjack_risk_engine.decisions import Decision, get_legal_actions
from blackjack_risk_engine.hand import CardInput, Hand, parse_card, parse_cards
from blackjack_risk_engine.risk import BettingRiskProfile, suggest_bet
from blackjack_risk_engine.rules import GameRules
from blackjack_risk_engine.simulation import GameState, simulate_round
from blackjack_risk_engine.strategy import recommend_basic_strategy


@dataclass(frozen=True, slots=True)
class ExpectedValue:
    decision: Decision
    value: float
    simulations: int = 0


def best_expected_value(values: list[ExpectedValue]) -> ExpectedValue:
    if not values:
        raise ValueError("values must not be empty")
    return max(values, key=lambda item: item.value)


@dataclass(frozen=True, slots=True)
class ActionAnalysis:
    action: Decision
    expected_value: float
    simulations: int
    wins: int
    losses: int
    pushes: int
    win_rate: float
    lose_rate: float
    push_rate: float
    std_dev: float
    standard_error: float
    confidence_interval_95: tuple[float, float]


@dataclass(slots=True)
class _ShuffledDeck:
    cards: list[Card]

    def draw(self) -> Card:
        if not self.cards:
            raise IndexError("cannot draw from an empty simulation deck")
        return self.cards.pop()


def analyze_action(
    player_hand: Hand | Iterable[CardInput],
    dealer_up_card: CardInput,
    seen_cards: Iterable[CardInput],
    rules: GameRules | None,
    action: Decision | str,
    simulations: int,
    seed: int | None = None,
    base_cards: list[Card] | None = None,
) -> ActionAnalysis:
    if simulations <= 0:
        raise ValueError("simulations must be greater than zero")

    active_rules = rules or GameRules()
    parsed_action = _parse_supported_action(action)
    player = _copy_hand(player_hand)
    if parsed_action not in get_legal_actions(player, active_rules):
        raise ValueError(f"action {parsed_action.value} is not legal for this hand and rules")

    dealer_up = parse_card(dealer_up_card)
    parsed_seen_cards = parse_cards(seen_cards)
    base_simulation_cards = (
        list(base_cards)
        if base_cards is not None
        else _build_base_simulation_cards(
            player_hand=player,
            dealer_up_card=dealer_up,
            seen_cards=parsed_seen_cards,
            rules=active_rules,
        )
    )
    rng = random.Random(seed)

    total_outcome = 0.0
    total_squared_outcome = 0.0
    wins = 0
    losses = 0
    pushes = 0

    for _ in range(simulations):
        simulation_deck = _shuffle_simulation_deck(base_simulation_cards, rng)
        result = simulate_round(
            player_hand=player,
            dealer_up_card=dealer_up,
            deck=simulation_deck,
            rules=active_rules,
            action=parsed_action,
        )

        total_outcome += result.outcome
        total_squared_outcome += result.outcome * result.outcome
        if result.outcome > 0:
            wins += 1
        elif result.outcome < 0:
            losses += 1
        else:
            pushes += 1

    expected_value = total_outcome / simulations
    std_dev = _sample_std_dev(
        count=simulations,
        total=total_outcome,
        total_squared=total_squared_outcome,
    )
    standard_error = std_dev / sqrt(simulations)
    confidence_interval_95 = (
        expected_value - 1.96 * standard_error,
        expected_value + 1.96 * standard_error,
    )

    return ActionAnalysis(
        action=parsed_action,
        expected_value=expected_value,
        simulations=simulations,
        wins=wins,
        losses=losses,
        pushes=pushes,
        win_rate=wins / simulations,
        lose_rate=losses / simulations,
        push_rate=pushes / simulations,
        std_dev=std_dev,
        standard_error=standard_error,
        confidence_interval_95=confidence_interval_95,
    )


def analyze_hand(
    player_hand: Hand | Iterable[CardInput],
    dealer_up_card: CardInput,
    seen_cards: Iterable[CardInput],
    rules: GameRules | None,
    simulations: int,
    seed: int | None = None,
    minimum_bet: float = 10.0,
    bankroll: float = 1000.0,
    risk_profile: BettingRiskProfile = "moderate",
) -> dict:
    start_time = time.perf_counter()
    active_rules = rules or GameRules()
    player = _copy_hand(player_hand)
    dealer_up = parse_card(dealer_up_card)
    parsed_seen_cards = parse_cards(seen_cards)
    known_cards = [*parsed_seen_cards, *player.cards, dealer_up]
    count_analysis = analyze_count(known_cards, active_rules)
    betting = suggest_bet(
        true_count=count_analysis.true_count,
        minimum_bet=minimum_bet,
        bankroll=bankroll,
        risk_profile=risk_profile,
    )
    base_simulation_cards = _build_base_simulation_cards(
        player_hand=player,
        dealer_up_card=dealer_up,
        seen_cards=parsed_seen_cards,
        rules=active_rules,
    )
    rng = random.Random(seed)
    analyses = [
        analyze_action(
            player_hand=player,
            dealer_up_card=dealer_up,
            seen_cards=parsed_seen_cards,
            rules=active_rules,
            action=action,
            simulations=simulations,
            seed=rng.randrange(2**32),
            base_cards=base_simulation_cards,
        )
        for action in get_legal_actions(player, active_rules)
    ]
    sorted_analyses = sorted(analyses, key=lambda analysis: analysis.expected_value, reverse=True)
    basic_strategy_action = recommend_basic_strategy(player, dealer_up, active_rules)
    execution_time_ms = (time.perf_counter() - start_time) * 1000

    return {
        "input": {
            "player": player.card_values,
            "dealer": dealer_up.rank.value,
            "seen": [card.rank.value for card in parsed_seen_cards],
        },
        "rules": _rules_to_dict(active_rules),
        "hand_analysis": {
            "cards": player.card_values,
            "total": player.total,
            "is_soft": player.is_soft,
            "is_bust": player.is_bust,
            "is_blackjack": player.is_blackjack,
            "is_pair": player.is_pair,
            "can_split": player.can_split,
        },
        "counting": {
            "running_count": count_analysis.running_count,
            "true_count": count_analysis.true_count,
            "cards_remaining": count_analysis.cards_remaining,
            "deck_status": count_analysis.deck_status,
        },
        "actions": [_action_analysis_to_dict(analysis) for analysis in sorted_analyses],
        "recommendation": {
            "best_action": sorted_analyses[0].action.value,
            "monte_carlo_action": sorted_analyses[0].action.value,
            "basic_strategy_action": basic_strategy_action.value,
            "strategy_agreement": sorted_analyses[0].action is basic_strategy_action,
            "confidence": _recommendation_confidence(sorted_analyses),
            "explanation": _recommendation_explanation_json(sorted_analyses, basic_strategy_action),
        },
        "betting": {
            "suggested_bet": betting.suggested_bet,
            "bet_units": betting.bet_units,
            "risk_profile": betting.risk_profile,
            "explanation": betting.explanation,
        },
        "metadata": {
            "engine_version": __version__,
            "simulation_seed": seed,
            "simulations": simulations,
            "execution_time_ms": round(execution_time_ms, 3),
        },
    }


def _parse_supported_action(action: Decision | str) -> Decision:
    try:
        parsed_action = action if isinstance(action, Decision) else Decision(action)
    except ValueError as error:
        raise ValueError("action must be one of: hit, stand, double, split, surrender") from error

    if parsed_action not in {
        Decision.HIT,
        Decision.STAND,
        Decision.DOUBLE,
        Decision.SPLIT,
        Decision.SURRENDER,
    }:
        raise ValueError("action must be one of: hit, stand, double, split, surrender")
    return parsed_action


def _copy_hand(hand: Hand | Iterable[CardInput]) -> Hand:
    if isinstance(hand, Hand):
        return Hand(hand.cards)
    return Hand(hand)


def _sample_std_dev(count: int, total: float, total_squared: float) -> float:
    if count <= 1:
        return 0.0

    variance = (total_squared - (total * total / count)) / (count - 1)
    return sqrt(max(variance, 0.0))


def _rules_to_dict(rules: GameRules) -> dict:
    return {
        "number_of_decks": rules.number_of_decks,
        "dealer_hits_soft_17": rules.dealer_hits_soft_17,
        "blackjack_payout": rules.blackjack_payout,
        "blackjack_payout_multiplier": rules.blackjack_payout_multiplier,
        "double_allowed": rules.double_allowed,
        "double_after_split": rules.double_after_split,
        "surrender_allowed": rules.surrender_allowed,
        "max_splits": rules.max_splits,
        "dealer_peek": rules.dealer_peek,
        "hit_split_aces": rules.hit_split_aces,
        "resplit_aces": rules.resplit_aces,
    }


def _action_analysis_to_dict(analysis: ActionAnalysis) -> dict:
    ci_low, ci_high = analysis.confidence_interval_95
    return {
        "action": analysis.action.value,
        "ev": analysis.expected_value,
        "win_rate": analysis.win_rate,
        "lose_rate": analysis.lose_rate,
        "push_rate": analysis.push_rate,
        "simulations": analysis.simulations,
        "wins": analysis.wins,
        "losses": analysis.losses,
        "pushes": analysis.pushes,
        "std_dev": analysis.std_dev,
        "standard_error": analysis.standard_error,
        "confidence_interval_95": [ci_low, ci_high],
    }


def _recommendation_confidence(analyses: list[ActionAnalysis]) -> float:
    if len(analyses) == 1:
        return 1.0

    best = analyses[0]
    runner_up = analyses[1]
    gap = best.expected_value - runner_up.expected_value
    uncertainty = best.standard_error + runner_up.standard_error
    if uncertainty <= 0:
        return 1.0 if gap > 0 else 0.5
    return round(max(0.0, min(1.0, gap / (gap + uncertainty))), 4)


def _recommendation_explanation(analyses: list[ActionAnalysis], basic_strategy_action: Decision) -> str:
    best = analyses[0]
    agreement_text = "concordam" if best.action is basic_strategy_action else "divergem"
    return (
        f"Melhor ação por EV Monte Carlo: {best.action.value}. "
        f"A estratégia básica simplificada recomenda {basic_strategy_action.value}; "
        f"as abordagens {agreement_text}. Confiança é uma aproximação baseada no gap de EV "
        "contra a incerteza amostral."
    )


def _build_simulation_deck(
    player_hand: Hand,
    dealer_up_card: Card,
    seen_cards: list[Card],
    rules: GameRules,
    rng: random.Random,
) -> _ShuffledDeck:
    shoe = Shoe(deck_count=rules.number_of_decks)
    shoe.remove_seen_cards(seen_cards)
    shoe.remove_seen_cards(player_hand.cards)
    shoe.remove_card(dealer_up_card)

    cards = list(shoe.cards)
    rng.shuffle(cards)
    return _ShuffledDeck(cards)


def _recommendation_explanation_json(analyses: list[ActionAnalysis], basic_strategy_action: Decision) -> str:
    best = analyses[0]
    agreement_text = "concordam" if best.action is basic_strategy_action else "divergem"
    return (
        f"Melhor acao por EV Monte Carlo: {best.action.value}. "
        f"A estrategia basica simplificada recomenda {basic_strategy_action.value}; "
        f"as abordagens {agreement_text}. Confianca e uma aproximacao baseada no gap de EV "
        "contra a incerteza amostral."
    )


def _build_base_simulation_cards(
    player_hand: Hand,
    dealer_up_card: Card,
    seen_cards: list[Card],
    rules: GameRules,
) -> list[Card]:
    shoe = Shoe(deck_count=rules.number_of_decks)
    shoe.remove_seen_cards(seen_cards)
    shoe.remove_seen_cards(player_hand.cards)
    shoe.remove_card(dealer_up_card)
    return list(shoe.cards)


def _shuffle_simulation_deck(cards: list[Card], rng: random.Random) -> _ShuffledDeck:
    shuffled_cards = list(cards)
    rng.shuffle(shuffled_cards)
    return _ShuffledDeck(shuffled_cards)


class MonteCarloActionAnalyzer:
    def __init__(self, simulations: int = 10_000, seed: int | None = None) -> None:
        self.simulations = simulations
        self.seed = seed

    def analyze(self, state: GameState, action: Decision | str) -> ActionAnalysis:
        return analyze_action(
            player_hand=state.player_hand,
            dealer_up_card=state.dealer_up_card,
            seen_cards=state.seen_cards,
            rules=state.rules,
            action=action,
            simulations=self.simulations,
            seed=self.seed,
        )
