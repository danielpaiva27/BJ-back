from __future__ import annotations

import random
import time
import zlib
from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass, replace
from enum import Enum
from math import fsum, isfinite

from blackjack_risk_engine.decisions import Decision, get_legal_actions
from blackjack_risk_engine.engine_core.adapters import (
    core_rules_to_game_rules,
    ranks_to_cards,
)
from blackjack_risk_engine.engine_core.action_ev import (
    DeterministicEvCacheLimitExceeded,
    calculate_action_evs_deterministic,
)
from blackjack_risk_engine.engine_core.cards import (
    RANK_STRINGS,
    deck_counts_for_decks,
    string_to_rank,
)
from blackjack_risk_engine.engine_core.engine_mode import (
    EngineMode,
    normalize_engine_mode,
)
from blackjack_risk_engine.engine_core.monte_carlo_analysis import (
    monte_carlo_analysis,
)
from blackjack_risk_engine.engine_core.pre_round.machine_ev.config import (
    MachineEvConfig,
)
from blackjack_risk_engine.engine_core.pre_round.machine_ev.models import (
    MachineEvInitialState,
    MachineEvInput,
    MachineEvInternalMetrics,
    MachineEvMinimumBetDiagnostics,
    MachineEvPublicSummary,
    MachineEvResult,
    MachineEvStateEvaluation,
)
from blackjack_risk_engine.engine_core.pre_round.machine_ev.predeal_enumerator import (
    enumerate_observable_initial_states,
)
from blackjack_risk_engine.engine_core.pre_round.bankroll_policy import (
    calculate_minimum_bankroll_for_bet_at_risk_limit,
    estimate_risk_of_ruin,
)
from blackjack_risk_engine.engine_core.rules import CoreRules
from blackjack_risk_engine.engine_core.state import CoreGameState
from blackjack_risk_engine.hand import Hand
from blackjack_risk_engine.rules import GameRules


MACHINE_EV_DECISION_SIMULATIONS = 100
MACHINE_EV_DETERMINISTIC_CACHE_STATES = 1

_DIAGNOSTIC_TEXT = {
    "not_evaluated": "A Machine EV ainda não foi calculada.",
    "missing_wager_inputs": (
        "A vantagem foi estimada, mas faltam dados de banca ou aposta mínima "
        "para completar o diagnóstico de risco."
    ),
    "invalid_bankroll": (
        "A banca informada é inválida para calcular o risco da aposta mínima."
    ),
    "non_positive_edge": (
        "Sem vantagem positiva estimada, não há banca finita que torne a "
        "aposta mínima favorável por este modelo."
    ),
    "minimum_bet_within_risk_limit": (
        "A aposta mínima fica dentro do limite aproximado de risco usando a "
        "vantagem estimada pela Machine EV."
    ),
    "minimum_bet_exceeds_risk_limit": (
        "A vantagem estimada é positiva, mas a aposta mínima excede o limite "
        "aproximado de risco para a banca atual."
    ),
}


def make_machine_ev_rules_signature(
    rules: Mapping[str, object] | object | None,
) -> tuple[tuple[str, object], ...]:
    if rules is None:
        return ()

    if isinstance(rules, Mapping):
        rule_values = dict(rules)
    elif is_dataclass(rules) and not isinstance(rules, type):
        rule_values = asdict(rules)
    else:
        model_dump = getattr(rules, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            if not isinstance(dumped, Mapping):
                raise ValueError("rules.model_dump() must return a mapping")
            rule_values = dict(dumped)
        else:
            object_values = getattr(rules, "__dict__", None)
            if not isinstance(object_values, Mapping):
                raise ValueError(
                    "rules must be a mapping, dataclass, Pydantic model, or simple object"
                )
            rule_values = {
                key: value
                for key, value in object_values.items()
                if not key.startswith("_")
            }

    if any(not isinstance(key, str) for key in rule_values):
        raise ValueError("rules signature keys must be strings")
    return tuple(
        (key, _freeze_rules_signature_value(rule_values[key]))
        for key in sorted(rule_values)
    )


def aggregate_machine_ev_state_evaluations(
    weighted_items: Iterable[tuple[float, float]],
) -> float:
    weighted_values: list[float] = []
    for probability, state_ev in weighted_items:
        if (
            isinstance(probability, bool)
            or not isinstance(probability, (int, float))
            or not isfinite(probability)
            or probability < 0
        ):
            raise ValueError("state probability must be finite and non-negative")
        if (
            isinstance(state_ev, bool)
            or not isinstance(state_ev, (int, float))
            or not isfinite(state_ev)
        ):
            raise ValueError("state EV must be finite")
        weighted_values.append(probability * state_ev)

    aggregated_ev = fsum(weighted_values)
    if not isfinite(aggregated_ev):
        raise ValueError("aggregated Machine EV must be finite")
    return aggregated_ev


def build_machine_ev_shoe_counts(
    number_of_decks: int,
    seen_cards: Iterable[str],
) -> dict[str, int]:
    if (
        isinstance(number_of_decks, bool)
        or not isinstance(number_of_decks, int)
        or number_of_decks <= 0
    ):
        raise ValueError("number_of_decks must be a positive integer")
    if isinstance(seen_cards, (str, bytes)):
        raise ValueError("seen_cards must be an iterable of blackjack ranks")

    counts = list(deck_counts_for_decks(number_of_decks))
    for card in tuple(seen_cards):
        if not isinstance(card, str):
            raise ValueError("seen_cards must contain blackjack rank strings")
        rank = string_to_rank(card)
        counts[rank] -= 1
        if counts[rank] < 0:
            raise ValueError(
                f"seen_cards removes more {RANK_STRINGS[rank]} cards than the shoe contains"
            )

    return dict(zip(RANK_STRINGS, counts, strict=True))


def calculate_machine_ev_minimum_bet_diagnostics(
    estimated_next_hand_edge: float | None,
    bankroll: float | None,
    minimum_bet: float | None,
    config: MachineEvConfig,
) -> MachineEvMinimumBetDiagnostics:
    if not isinstance(config, MachineEvConfig):
        raise ValueError("config must be a MachineEvConfig")
    if minimum_bet is not None and (
        isinstance(minimum_bet, bool)
        or not isinstance(minimum_bet, (int, float))
        or not isfinite(minimum_bet)
        or minimum_bet <= 0
    ):
        raise ValueError("minimum_bet must be a positive finite number")
    if estimated_next_hand_edge is not None and (
        isinstance(estimated_next_hand_edge, bool)
        or not isinstance(estimated_next_hand_edge, (int, float))
        or not isfinite(estimated_next_hand_edge)
    ):
        raise ValueError("estimated_next_hand_edge must be a finite number or None")

    base_values = {
        "risk_of_ruin_limit": config.risk_of_ruin_limit,
        "variance_per_unit": config.variance_per_unit_fallback,
    }
    if estimated_next_hand_edge is None:
        return MachineEvMinimumBetDiagnostics(
            risk_if_minimum_bet=None,
            minimum_bankroll_required_for_minimum_bet=None,
            minimum_bet_exceeds_risk_cap=None,
            diagnostic_status="not_evaluated",
            diagnostic_text=_DIAGNOSTIC_TEXT["not_evaluated"],
            **base_values,
        )

    minimum_bankroll_required = (
        calculate_minimum_bankroll_for_bet_at_risk_limit(
            bet_amount=minimum_bet,
            estimated_player_edge=estimated_next_hand_edge,
            risk_of_ruin_limit=config.risk_of_ruin_limit,
            variance_per_unit=config.variance_per_unit_fallback,
        )
        if minimum_bet is not None and estimated_next_hand_edge > 0
        else None
    )
    if bankroll is None or minimum_bet is None:
        return MachineEvMinimumBetDiagnostics(
            risk_if_minimum_bet=None,
            minimum_bankroll_required_for_minimum_bet=minimum_bankroll_required,
            minimum_bet_exceeds_risk_cap=None,
            diagnostic_status="missing_wager_inputs",
            diagnostic_text=_DIAGNOSTIC_TEXT["missing_wager_inputs"],
            **base_values,
        )
    if (
        isinstance(bankroll, bool)
        or not isinstance(bankroll, (int, float))
        or not isfinite(bankroll)
        or bankroll <= 0
    ):
        return MachineEvMinimumBetDiagnostics(
            risk_if_minimum_bet=None,
            minimum_bankroll_required_for_minimum_bet=None,
            minimum_bet_exceeds_risk_cap=None,
            diagnostic_status="invalid_bankroll",
            diagnostic_text=_DIAGNOSTIC_TEXT["invalid_bankroll"],
            **base_values,
        )
    if estimated_next_hand_edge <= 0:
        return MachineEvMinimumBetDiagnostics(
            risk_if_minimum_bet=estimate_risk_of_ruin(
                bankroll=bankroll,
                bet_amount=minimum_bet,
                estimated_player_edge=estimated_next_hand_edge,
                variance_per_unit=config.variance_per_unit_fallback,
            ),
            minimum_bankroll_required_for_minimum_bet=None,
            minimum_bet_exceeds_risk_cap=True,
            diagnostic_status="non_positive_edge",
            diagnostic_text=_DIAGNOSTIC_TEXT["non_positive_edge"],
            **base_values,
        )

    risk_if_minimum_bet = estimate_risk_of_ruin(
        bankroll=bankroll,
        bet_amount=minimum_bet,
        estimated_player_edge=estimated_next_hand_edge,
        variance_per_unit=config.variance_per_unit_fallback,
    )
    exceeds_risk_limit = risk_if_minimum_bet > config.risk_of_ruin_limit
    diagnostic_status = (
        "minimum_bet_exceeds_risk_limit"
        if exceeds_risk_limit
        else "minimum_bet_within_risk_limit"
    )
    return MachineEvMinimumBetDiagnostics(
        risk_if_minimum_bet=risk_if_minimum_bet,
        minimum_bankroll_required_for_minimum_bet=minimum_bankroll_required,
        minimum_bet_exceeds_risk_cap=exceeds_risk_limit,
        diagnostic_status=diagnostic_status,
        diagnostic_text=_DIAGNOSTIC_TEXT[diagnostic_status],
        **base_values,
    )


def evaluate_initial_state_with_decision_engine(
    state: MachineEvInitialState,
    machine_input: MachineEvInput,
    config: MachineEvConfig,
) -> MachineEvStateEvaluation:
    core_rules = _build_core_rules(machine_input)
    mode = normalize_engine_mode(config.decision_engine_mode)
    player_ranks = tuple(string_to_rank(card) for card in state.player_cards)
    dealer_upcard_rank = string_to_rank(state.dealer_upcard)
    seen_ranks = tuple(string_to_rank(card) for card in machine_input.seen_cards)
    deck_counts = tuple(count for _, count in state.shoe_after)
    core_state = CoreGameState(
        player_ranks=player_ranks,
        dealer_upcard_rank=dealer_upcard_rank,
        seen_ranks=seen_ranks,
        deck_counts=deck_counts,
        rules=core_rules,
    )

    active_rules = core_rules_to_game_rules(core_rules)
    player = Hand(ranks_to_cards(player_ranks))
    legal_actions = get_legal_actions(player, active_rules)
    seed = _stable_state_seed(state)
    action_evs = _evaluate_action_evs(
        mode=mode,
        state=core_state,
        active_rules=active_rules,
        legal_actions=legal_actions,
        seed=seed,
    )
    if not action_evs:
        raise ValueError("decision engine returned no evaluable actions")

    ranked_action_evs = tuple(
        sorted(action_evs, key=lambda item: item[1], reverse=True)
    )
    best_action, best_ev = ranked_action_evs[0]
    return MachineEvStateEvaluation(
        player_cards=state.player_cards,
        dealer_upcard=state.dealer_upcard,
        probability=state.probability,
        best_action=best_action,
        state_ev=best_ev,
        action_evs=ranked_action_evs,
    )


def evaluate_machine_ev_pre_round(
    machine_input: MachineEvInput,
    config: MachineEvConfig | None = None,
) -> MachineEvResult:
    if not isinstance(machine_input, MachineEvInput):
        raise ValueError("machine_input must be a MachineEvInput")
    if config is not None and not isinstance(config, MachineEvConfig):
        raise ValueError("config must be a MachineEvConfig or None")

    active_config = config or MachineEvConfig()
    if not active_config.enabled:
        return MachineEvResult(
            metrics=MachineEvInternalMetrics(
                warnings=("Machine EV evaluation is disabled by config.",),
            ),
            config=active_config,
        )

    start_time = time.perf_counter()
    core_rules = _build_core_rules(machine_input)
    engine_mode = normalize_engine_mode(active_config.decision_engine_mode)
    rules_signature = make_machine_ev_rules_signature(core_rules)
    shoe_counts = build_machine_ev_shoe_counts(
        machine_input.number_of_decks,
        machine_input.seen_cards,
    )

    states = enumerate_observable_initial_states(shoe_counts, active_config)
    evaluations: list[MachineEvStateEvaluation] = []
    warnings: list[str] = []
    evaluation_cache: dict[
        tuple[object, str, tuple[tuple[str, object], ...]],
        MachineEvStateEvaluation,
    ] = {}
    cache_hits = 0
    cache_misses = 0

    for state in states:
        cache_key = (
            state.canonical_key,
            engine_mode,
            rules_signature,
        )
        cached_evaluation = (
            evaluation_cache.get(cache_key)
            if active_config.use_cache
            else None
        )
        if cached_evaluation is not None:
            cache_hits += 1
            evaluation = replace(
                cached_evaluation,
                probability=state.probability,
            )
        else:
            try:
                evaluation = evaluate_initial_state_with_decision_engine(
                    state,
                    machine_input,
                    active_config,
                )
            except (IndexError, ValueError) as error:
                raise ValueError(
                    "Unable to evaluate observable state "
                    f"{state.player_cards} against dealer {state.dealer_upcard}: {error}"
                ) from error
            if active_config.use_cache:
                cache_misses += 1
                evaluation_cache[cache_key] = evaluation
        evaluations.append(evaluation)
        if evaluation.warning:
            warnings.append(evaluation.warning)

    machine_ev = aggregate_machine_ev_state_evaluations(
        (state.probability, evaluation.state_ev)
        for state, evaluation in zip(states, evaluations, strict=True)
    )
    if not isfinite(machine_ev):
        raise ValueError("Machine EV evaluation produced a non-finite result")

    diagnostics = calculate_machine_ev_minimum_bet_diagnostics(
        estimated_next_hand_edge=machine_ev,
        bankroll=machine_input.bankroll,
        minimum_bet=machine_input.minimum_bet,
        config=active_config,
    )
    duration_ms = max(
        0.0,
        (time.perf_counter() - start_time) * 1000,
    )
    if not isfinite(duration_ms):
        raise ValueError("Machine EV duration must be finite")
    timed_out = duration_ms > active_config.max_duration_ms
    if timed_out:
        warnings.append(
            "Machine EV exceeded configured duration budget; "
            "result remains exact but may be slow."
        )

    summary = MachineEvPublicSummary(
        estimated_next_hand_edge=machine_ev,
        risk_if_minimum_bet=diagnostics.risk_if_minimum_bet,
        minimum_bankroll_required_for_minimum_bet=(
            diagnostics.minimum_bankroll_required_for_minimum_bet
        ),
        recommendation_status=f"machine_ev_{diagnostics.diagnostic_status}",
        recommendation_text=diagnostics.diagnostic_text,
    )
    metrics = MachineEvInternalMetrics(
        states_evaluated=len(states),
        duration_ms=duration_ms,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        timed_out=timed_out,
        warnings=tuple(warnings),
    )
    return MachineEvResult(
        summary=summary,
        metrics=metrics,
        config=active_config,
        raw_ev_per_unit=machine_ev,
        variance_per_unit=active_config.variance_per_unit_fallback,
        state_evaluations=(
            tuple(evaluations)
            if active_config.include_state_breakdown
            else None
        ),
    )


def _freeze_rules_signature_value(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("rules signature cannot contain NaN or Infinity")
        return value
    if isinstance(value, Enum):
        return _freeze_rules_signature_value(value.value)
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("nested rules signature keys must be strings")
        return tuple(
            (key, _freeze_rules_signature_value(value[key]))
            for key in sorted(value)
        )
    if is_dataclass(value) and not isinstance(value, type):
        return _freeze_rules_signature_value(asdict(value))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_rules_signature_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        frozen_items = tuple(
            _freeze_rules_signature_value(item)
            for item in value
        )
        return tuple(sorted(frozen_items, key=repr))

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _freeze_rules_signature_value(model_dump())
    object_values = getattr(value, "__dict__", None)
    if isinstance(object_values, Mapping):
        return _freeze_rules_signature_value(
            {
                key: nested_value
                for key, nested_value in object_values.items()
                if isinstance(key, str) and not key.startswith("_")
            }
        )
    raise ValueError(
        f"rules signature contains unsupported value type: {type(value).__name__}"
    )


def _build_core_rules(machine_input: MachineEvInput) -> CoreRules:
    if machine_input.rules is not None and not isinstance(machine_input.rules, Mapping):
        raise ValueError("rules must be a mapping or None")

    rule_values = dict(machine_input.rules or {})
    configured_decks = rule_values.get("number_of_decks")
    if configured_decks is not None and configured_decks != machine_input.number_of_decks:
        raise ValueError("rules.number_of_decks must match MachineEvInput.number_of_decks")
    rule_values["number_of_decks"] = machine_input.number_of_decks

    try:
        return CoreRules(**rule_values)
    except TypeError as error:
        raise ValueError(f"invalid Machine EV rules: {error}") from error


def _stable_state_seed(state: MachineEvInitialState) -> int:
    key_bytes = repr(state.canonical_key).encode("ascii")
    return zlib.crc32(key_bytes)


def _evaluate_action_evs(
    *,
    mode: EngineMode,
    state: CoreGameState,
    active_rules: GameRules,
    legal_actions: tuple[Decision, ...],
    seed: int,
) -> tuple[tuple[str, float], ...]:
    action_names = tuple(action.value for action in legal_actions)
    rng = random.Random(seed)
    action_seeds = {action.value: rng.randrange(2**32) for action in legal_actions}

    if mode == "deterministic":
        ranking = calculate_action_evs_deterministic(state, action_names)
        return tuple((result.action, result.ev) for result in ranking.actions)

    if mode == "hybrid":
        results: list[tuple[str, float]] = []
        for action in action_names:
            try:
                ranking = calculate_action_evs_deterministic(
                    state,
                    (action,),
                    max_cache_states=MACHINE_EV_DETERMINISTIC_CACHE_STATES,
                )
            except DeterministicEvCacheLimitExceeded:
                ranking = None

            if ranking is not None and ranking.actions:
                result = ranking.actions[0]
                results.append((result.action, result.ev))
            else:
                results.extend(
                    _evaluate_actions_monte_carlo(
                        state,
                        (action,),
                        action_seeds,
                    )
                )
        return tuple(results)

    if mode == "monte_carlo":
        return _evaluate_actions_monte_carlo(
            state,
            action_names,
            action_seeds,
        )

    action_seed_by_decision = {
        action: action_seeds[action.value]
        for action in legal_actions
    }
    # Legacy mode lives in the public orchestration module; default modes stay core-only.
    from blackjack_risk_engine.ev import _run_engine_mode

    mode_result = _run_engine_mode(
        mode=mode,
        state=state,
        active_rules=active_rules,
        legal_actions=legal_actions,
        simulations=MACHINE_EV_DECISION_SIMULATIONS,
        action_seeds=action_seed_by_decision,
        monte_carlo_config=None,
    )
    return tuple(
        (analysis.action.value, analysis.expected_value)
        for analysis in mode_result.analyses
    )


def _evaluate_actions_monte_carlo(
    state: CoreGameState,
    actions: tuple[str, ...],
    action_seeds: dict[str, int],
) -> tuple[tuple[str, float], ...]:
    return tuple(
        (
            action,
            monte_carlo_analysis(
                state=state,
                action=action,
                simulations=MACHINE_EV_DECISION_SIMULATIONS,
                seed=action_seeds[action],
            ).stats.expected_value,
        )
        for action in actions
    )
