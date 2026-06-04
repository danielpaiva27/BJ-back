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
from blackjack_risk_engine.engine_core.action_ev import (
    ActionEvResult,
    DeterministicEvCacheLimitExceeded,
)
from blackjack_risk_engine.engine_core.adapters import (
    build_analyze_hand_response,
    build_core_state_from_inputs,
    core_rules_to_game_rules,
    core_rules_to_public_dict,
    rank_to_card,
    ranks_to_cards,
)
from blackjack_risk_engine.engine_core.dealer_dp import dealer_distribution_cache_info
from blackjack_risk_engine.engine_core.deterministic_analysis import deterministic_analysis
from blackjack_risk_engine.engine_core.engine_mode import EngineMode, normalize_engine_mode
from blackjack_risk_engine.engine_core.hybrid_analysis import hybrid_analysis
from blackjack_risk_engine.engine_core.monte_carlo_analysis import (
    MonteCarloActionResult,
    MonteCarloConfig,
    monte_carlo_analysis,
)
from blackjack_risk_engine.engine_core.state import CoreGameState, remaining_ordered_ranks_for_state
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


@dataclass(frozen=True, slots=True)
class _EngineModeRun:
    analyses: list[ActionAnalysis]
    analysis_method: str
    deterministic_actions: tuple[str, ...]
    monte_carlo_actions: tuple[str, ...]
    unsupported_actions: tuple[str, ...]
    deterministic_cache_states: int
    simulations_used: int


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
    monte_carlo_config: MonteCarloConfig | None = None,
    engine_mode: EngineMode | str | None = None,
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
    state = build_core_state_from_inputs(player, dealer_up, parsed_seen_cards, active_rules)
    mode = normalize_engine_mode(engine_mode)

    if mode in {"hybrid", "deterministic"} and parsed_action.value in {"hit", "stand", "double", "surrender"}:
        try:
            ranking = deterministic_analysis(state, (parsed_action.value,))
            if ranking.actions:
                return _action_ev_result_to_analysis(ranking.actions[0], Decision(parsed_action.value), simulations)
        except DeterministicEvCacheLimitExceeded:
            pass

    if mode == "deterministic":
        raise ValueError(f"action {parsed_action.value} is not supported by deterministic engine mode")

    if mode == "legacy":
        return _analyze_action_legacy_monte_carlo(
            state=state,
            active_rules=active_rules,
            parsed_action=parsed_action,
            simulations=simulations,
            seed=seed,
            base_cards=base_cards,
        )

    return _analyze_action_monte_carlo(
        state=state,
        parsed_action=parsed_action,
        simulations=simulations,
        seed=seed,
        config=monte_carlo_config,
    )


def _analyze_action_monte_carlo(
    state: CoreGameState,
    parsed_action: Decision,
    simulations: int,
    seed: int | None = None,
    config: MonteCarloConfig | None = None,
) -> ActionAnalysis:
    result = monte_carlo_analysis(
        state=state,
        action=parsed_action.value,
        simulations=simulations,
        seed=seed,
        config=config,
    )
    return _monte_carlo_result_to_analysis(result, parsed_action)


def _analyze_action_legacy_monte_carlo(
    state: CoreGameState,
    active_rules: GameRules,
    parsed_action: Decision,
    simulations: int,
    seed: int | None = None,
    base_cards: list[Card] | None = None,
) -> ActionAnalysis:
    player = Hand(ranks_to_cards(state.player_ranks))
    dealer_up = rank_to_card(state.dealer_upcard_rank)
    base_simulation_cards = (
        list(base_cards)
        if base_cards is not None
        else _build_base_simulation_cards_from_core_state(state)
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


def _monte_carlo_result_to_analysis(
    result: MonteCarloActionResult,
    action: Decision,
) -> ActionAnalysis:
    stats = result.stats
    expected_value = stats.expected_value
    std_dev = stats.std_dev
    standard_error = std_dev / sqrt(stats.simulations)
    confidence_interval_95 = (
        expected_value - 1.96 * standard_error,
        expected_value + 1.96 * standard_error,
    )

    return ActionAnalysis(
        action=action,
        expected_value=expected_value,
        simulations=stats.simulations,
        wins=stats.wins,
        losses=stats.losses,
        pushes=stats.pushes,
        win_rate=stats.wins / stats.simulations,
        lose_rate=stats.losses / stats.simulations,
        push_rate=stats.pushes / stats.simulations,
        std_dev=std_dev,
        standard_error=standard_error,
        confidence_interval_95=confidence_interval_95,
    )


def _action_ev_result_to_analysis(
    result: ActionEvResult,
    action: Decision,
    simulations: int,
) -> ActionAnalysis:
    wins, losses, pushes = _probability_counts(
        probabilities=(result.win_rate, result.lose_rate, result.push_rate),
        total=simulations,
    )

    return ActionAnalysis(
        action=action,
        expected_value=result.ev,
        simulations=simulations,
        wins=wins,
        losses=losses,
        pushes=pushes,
        win_rate=result.win_rate,
        lose_rate=result.lose_rate,
        push_rate=result.push_rate,
        std_dev=result.std_dev,
        standard_error=0.0,
        confidence_interval_95=(result.ev, result.ev),
    )


def _run_engine_mode(
    mode: EngineMode,
    state: CoreGameState,
    active_rules: GameRules,
    legal_actions: tuple[Decision, ...],
    simulations: int,
    action_seeds: dict[Decision, int],
    monte_carlo_config: MonteCarloConfig | None,
) -> _EngineModeRun:
    action_names = tuple(action.value for action in legal_actions)

    if mode == "legacy":
        analyses = [
            _analyze_action_legacy_monte_carlo(
                state=state,
                active_rules=active_rules,
                parsed_action=action,
                simulations=simulations,
                seed=action_seeds[action],
            )
            for action in legal_actions
        ]
        return _EngineModeRun(
            analyses=analyses,
            analysis_method="legacy_monte_carlo",
            deterministic_actions=(),
            monte_carlo_actions=action_names,
            unsupported_actions=(),
            deterministic_cache_states=0,
            simulations_used=simulations * len(legal_actions),
        )

    if mode == "monte_carlo":
        analyses = [
            _analyze_action_monte_carlo(
                state=state,
                parsed_action=action,
                simulations=simulations,
                seed=action_seeds[action],
                config=monte_carlo_config,
            )
            for action in legal_actions
        ]
        return _EngineModeRun(
            analyses=analyses,
            analysis_method="optimized_monte_carlo",
            deterministic_actions=(),
            monte_carlo_actions=action_names,
            unsupported_actions=(),
            deterministic_cache_states=0,
            simulations_used=simulations * len(legal_actions),
        )

    if mode == "deterministic":
        ranking = deterministic_analysis(state, action_names)
        analyses = [
            _action_ev_result_to_analysis(result, Decision(result.action), simulations)
            for result in ranking.actions
        ]
        analysis_method = (
            "deterministic_dp"
            if not ranking.unsupported_actions
            else "deterministic_dp_unsupported_actions_ignored"
        )
        return _EngineModeRun(
            analyses=analyses,
            analysis_method=analysis_method,
            deterministic_actions=tuple(action.action for action in ranking.actions),
            monte_carlo_actions=(),
            unsupported_actions=ranking.unsupported_actions,
            deterministic_cache_states=ranking.cache_states,
            simulations_used=0,
        )

    plan = hybrid_analysis(state, action_names)
    analyses = (
        [
            _action_ev_result_to_analysis(result, Decision(result.action), simulations)
            for result in plan.deterministic_ranking.actions
        ]
        if plan.deterministic_ranking is not None
        else []
    )
    monte_carlo_actions = tuple(Decision(action) for action in plan.monte_carlo_actions)
    analyses.extend(
        _analyze_action_monte_carlo(
            state=state,
            parsed_action=action,
            simulations=simulations,
            seed=action_seeds[action],
            config=monte_carlo_config,
        )
        for action in monte_carlo_actions
    )
    return _EngineModeRun(
        analyses=analyses,
        analysis_method=_analysis_method(monte_carlo_actions, plan.fallback_reason),
        deterministic_actions=plan.deterministic_actions,
        monte_carlo_actions=plan.monte_carlo_actions,
        unsupported_actions=(),
        deterministic_cache_states=plan.deterministic_cache_states,
        simulations_used=simulations * len(monte_carlo_actions),
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
    core_state: CoreGameState | None = None,
    monte_carlo_config: MonteCarloConfig | None = None,
    engine_mode: EngineMode | str | None = None,
) -> dict:
    start_time = time.perf_counter()
    dealer_cache_start = dealer_distribution_cache_info()
    state = core_state or build_core_state_from_inputs(player_hand, dealer_up_card, seen_cards, rules)
    mode = normalize_engine_mode(engine_mode)
    active_rules = core_rules_to_game_rules(state.rules)
    player = Hand(ranks_to_cards(state.player_ranks))
    dealer_up = rank_to_card(state.dealer_upcard_rank)
    parsed_seen_cards = ranks_to_cards(state.seen_ranks)
    known_cards = [*parsed_seen_cards, *player.cards, dealer_up]
    count_analysis = analyze_count(known_cards, active_rules)
    betting = suggest_bet(
        true_count=count_analysis.true_count,
        minimum_bet=minimum_bet,
        bankroll=bankroll,
        risk_profile=risk_profile,
    )
    rng = random.Random(seed)
    legal_actions = get_legal_actions(player, active_rules)
    action_seeds = {action: rng.randrange(2**32) for action in legal_actions}
    mode_result = _run_engine_mode(
        mode=mode,
        state=state,
        active_rules=active_rules,
        legal_actions=legal_actions,
        simulations=simulations,
        action_seeds=action_seeds,
        monte_carlo_config=monte_carlo_config,
    )
    analyses = mode_result.analyses
    sorted_analyses = sorted(analyses, key=lambda analysis: analysis.expected_value, reverse=True)
    basic_strategy_action = recommend_basic_strategy(player, dealer_up, active_rules)
    execution_time_ms = (time.perf_counter() - start_time) * 1000
    dealer_cache_end = dealer_distribution_cache_info()

    actions = [_action_analysis_to_dict(analysis) for analysis in sorted_analyses]
    recommendation = {
        "best_action": sorted_analyses[0].action.value,
        "monte_carlo_action": sorted_analyses[0].action.value,
        "basic_strategy_action": basic_strategy_action.value,
        "strategy_agreement": sorted_analyses[0].action is basic_strategy_action,
        "confidence": _recommendation_confidence(sorted_analyses),
        "explanation": _recommendation_explanation_json(sorted_analyses, basic_strategy_action),
    }
    metadata = {
        "engine_version": __version__,
        "engine_mode": mode,
        "simulation_seed": seed,
        "simulations": simulations,
        "simulations_used": mode_result.simulations_used,
        "execution_time_ms": round(execution_time_ms, 3),
        "elapsed_ms": round(execution_time_ms, 3),
        "analysis_method": mode_result.analysis_method,
        "deterministic_actions": sorted(mode_result.deterministic_actions),
        "monte_carlo_fallback_actions": list(mode_result.monte_carlo_actions),
        "unsupported_actions": list(mode_result.unsupported_actions),
        "deterministic_cache_states": mode_result.deterministic_cache_states,
        "cache_hits": dealer_cache_end.hits - dealer_cache_start.hits,
        "cache_misses": dealer_cache_end.misses - dealer_cache_start.misses,
    }

    return build_analyze_hand_response(
        state=state,
        actions=actions,
        recommendation=recommendation,
        count_analysis=count_analysis,
        betting=betting,
        metadata=metadata,
    )


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


def _probability_counts(probabilities: tuple[float, float, float], total: int) -> tuple[int, int, int]:
    raw_counts = [max(0.0, probability) * total for probability in probabilities]
    counts = [int(value) for value in raw_counts]
    remainder = total - sum(counts)

    if remainder > 0:
        order = sorted(
            range(len(raw_counts)),
            key=lambda index: raw_counts[index] - counts[index],
            reverse=True,
        )
        for index in order[:remainder]:
            counts[index] += 1
    elif remainder < 0:
        order = sorted(
            range(len(raw_counts)),
            key=lambda index: raw_counts[index] - counts[index],
        )
        for index in order[: abs(remainder)]:
            counts[index] -= 1

    return counts[0], counts[1], counts[2]


def _analysis_method(
    fallback_actions: tuple[Decision, ...],
    deterministic_fallback_reason: str | None,
) -> str:
    if deterministic_fallback_reason:
        return "monte_carlo_fallback_cache_limit"
    if fallback_actions:
        return "deterministic_dp_with_monte_carlo_fallback"
    return "deterministic_dp"


def _rules_to_dict(rules: GameRules) -> dict:
    return core_rules_to_public_dict(rules)


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
        f"Melhor ação por EV calculado: {best.action.value}. "
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
        f"Melhor acao por EV calculado: {best.action.value}. "
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
    state = build_core_state_from_inputs(player_hand, dealer_up_card, seen_cards, rules)
    return _build_base_simulation_cards_from_core_state(state)


def _build_base_simulation_cards_from_core_state(state: CoreGameState) -> list[Card]:
    return ranks_to_cards(remaining_ordered_ranks_for_state(state))


def _shuffle_simulation_deck(cards: list[Card], rng: random.Random) -> _ShuffledDeck:
    shuffled_cards = list(cards)
    rng.shuffle(shuffled_cards)
    return _ShuffledDeck(shuffled_cards)


class MonteCarloActionAnalyzer:
    def __init__(
        self,
        simulations: int = 10_000,
        seed: int | None = None,
        config: MonteCarloConfig | None = None,
    ) -> None:
        self.simulations = simulations
        self.seed = seed
        self.config = config

    def analyze(self, state: GameState, action: Decision | str) -> ActionAnalysis:
        return analyze_action(
            player_hand=state.player_hand,
            dealer_up_card=state.dealer_up_card,
            seen_cards=state.seen_cards,
            rules=state.rules,
            action=action,
            simulations=self.simulations,
            seed=self.seed,
            monte_carlo_config=self.config,
        )
