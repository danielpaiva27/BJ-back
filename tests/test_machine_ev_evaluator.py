from dataclasses import fields
import inspect
import math

import pytest

from blackjack_risk_engine.engine_core.cards import ONE_DECK_COUNTS, RANK_STRINGS
from blackjack_risk_engine.engine_core.pre_round.machine_ev import (
    MachineEvConfig,
    MachineEvInitialState,
    MachineEvInput,
    MachineEvPublicSummary,
    MachineEvResult,
    MachineEvStateEvaluation,
    aggregate_machine_ev_state_evaluations,
    build_machine_ev_shoe_counts,
    calculate_machine_ev_minimum_bet_diagnostics,
    evaluate_machine_ev_pre_round,
    make_machine_ev_rules_signature,
)
from blackjack_risk_engine.engine_core.rules import CoreRules
import blackjack_risk_engine.engine_core.pre_round.machine_ev.evaluator as evaluator_module


def _state(
    *,
    player_cards: tuple[str, str],
    dealer_upcard: str,
    probability: float,
) -> MachineEvInitialState:
    signature = (0,) * len(RANK_STRINGS)
    return MachineEvInitialState(
        player_cards=player_cards,
        dealer_upcard=dealer_upcard,
        shoe_after=tuple(zip(RANK_STRINGS, signature, strict=True)),
        probability=probability,
        canonical_key=(player_cards, dealer_upcard, signature),
    )


def _full_shoe_cards(number_of_decks: int) -> list[str]:
    cards: list[str] = []
    for rank, count in zip(RANK_STRINGS, ONE_DECK_COUNTS, strict=True):
        cards.extend([rank] * count * number_of_decks)
    return cards


def _mock_machine_ev_edge(
    monkeypatch: pytest.MonkeyPatch,
    edge: float,
) -> None:
    states = (
        _state(player_cards=("8", "10"), dealer_upcard="6", probability=1.0),
    )
    monkeypatch.setattr(
        evaluator_module,
        "enumerate_observable_initial_states",
        lambda shoe_counts, config: states,
    )
    monkeypatch.setattr(
        evaluator_module,
        "evaluate_initial_state_with_decision_engine",
        lambda state, machine_input, config: MachineEvStateEvaluation(
            player_cards=state.player_cards,
            dealer_upcard=state.dealer_upcard,
            probability=state.probability,
            best_action="stand",
            state_ev=edge,
            action_evs=(("stand", edge),),
        ),
    )


def test_basic_machine_ev_result_is_finite() -> None:
    result = evaluate_machine_ev_pre_round(MachineEvInput(number_of_decks=1))

    assert isinstance(result, MachineEvResult)
    assert result.summary.model_id == "machine_ev"
    assert math.isfinite(result.summary.estimated_next_hand_edge)
    assert math.isfinite(result.raw_ev_per_unit)
    assert result.summary.estimated_next_hand_edge == result.raw_ev_per_unit
    assert result.summary.recommendation_status == "machine_ev_missing_wager_inputs"
    assert result.metrics.states_evaluated > 0
    assert result.metrics.duration_ms is not None
    assert math.isfinite(result.metrics.duration_ms)
    assert result.metrics.duration_ms >= 0
    assert result.summary.risk_if_minimum_bet is None
    assert result.summary.minimum_bankroll_required_for_minimum_bet is None
    assert result.variance_per_unit == 1.3
    assert result.state_evaluations is None


def test_duration_budget_within_limit_is_not_timed_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_machine_ev_edge(monkeypatch, 0.05)
    times = iter((100.0, 100.0005))
    monkeypatch.setattr(evaluator_module.time, "perf_counter", lambda: next(times))

    result = evaluate_machine_ev_pre_round(
        MachineEvInput(number_of_decks=1),
        MachineEvConfig(max_duration_ms=1000),
    )

    assert result.metrics.duration_ms == pytest.approx(0.5)
    assert result.metrics.timed_out is False
    assert not any("duration budget" in warning for warning in result.metrics.warnings)


def test_duration_budget_exceeded_keeps_complete_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_machine_ev_edge(monkeypatch, 0.05)
    times = iter((100.0, 100.010))
    monkeypatch.setattr(evaluator_module.time, "perf_counter", lambda: next(times))

    result = evaluate_machine_ev_pre_round(
        MachineEvInput(number_of_decks=1),
        MachineEvConfig(max_duration_ms=1),
    )

    assert result.metrics.duration_ms == pytest.approx(10.0)
    assert result.metrics.timed_out is True
    assert math.isfinite(result.raw_ev_per_unit)
    assert result.raw_ev_per_unit == pytest.approx(0.05)
    assert (
        "Machine EV exceeded configured duration budget; "
        "result remains exact but may be slow."
    ) in result.metrics.warnings


def test_local_cache_records_hits_and_real_adapter_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate_states = (
        _state(player_cards=("8", "10"), dealer_upcard="6", probability=0.25),
        _state(player_cards=("8", "10"), dealer_upcard="6", probability=0.75),
    )
    calls = 0
    monkeypatch.setattr(
        evaluator_module,
        "enumerate_observable_initial_states",
        lambda shoe_counts, config: duplicate_states,
    )

    def fake_evaluate(
        state: MachineEvInitialState,
        machine_input: MachineEvInput,
        config: MachineEvConfig,
    ) -> MachineEvStateEvaluation:
        nonlocal calls
        calls += 1
        return MachineEvStateEvaluation(
            player_cards=state.player_cards,
            dealer_upcard=state.dealer_upcard,
            probability=state.probability,
            best_action="stand",
            state_ev=0.2,
            action_evs=(("stand", 0.2),),
        )

    monkeypatch.setattr(
        evaluator_module,
        "evaluate_initial_state_with_decision_engine",
        fake_evaluate,
    )

    result = evaluate_machine_ev_pre_round(
        MachineEvInput(number_of_decks=1),
        MachineEvConfig(use_cache=True),
    )

    assert calls == 1
    assert result.metrics.states_evaluated == 2
    assert result.metrics.cache_hits == 1
    assert result.metrics.cache_misses == 1
    assert result.raw_ev_per_unit == pytest.approx(0.2)


def test_disabled_cache_records_no_hits_or_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate_states = (
        _state(player_cards=("8", "10"), dealer_upcard="6", probability=0.25),
        _state(player_cards=("8", "10"), dealer_upcard="6", probability=0.75),
    )
    calls = 0
    monkeypatch.setattr(
        evaluator_module,
        "enumerate_observable_initial_states",
        lambda shoe_counts, config: duplicate_states,
    )

    def fake_evaluate(
        state: MachineEvInitialState,
        machine_input: MachineEvInput,
        config: MachineEvConfig,
    ) -> MachineEvStateEvaluation:
        nonlocal calls
        calls += 1
        return MachineEvStateEvaluation(
            player_cards=state.player_cards,
            dealer_upcard=state.dealer_upcard,
            probability=state.probability,
            best_action="stand",
            state_ev=0.2,
            action_evs=(("stand", 0.2),),
        )

    monkeypatch.setattr(
        evaluator_module,
        "evaluate_initial_state_with_decision_engine",
        fake_evaluate,
    )

    result = evaluate_machine_ev_pre_round(
        MachineEvInput(number_of_decks=1),
        MachineEvConfig(use_cache=False),
    )

    assert calls == 2
    assert result.metrics.states_evaluated == 2
    assert result.metrics.cache_hits == 0
    assert result.metrics.cache_misses == 0


def test_rules_signature_is_stable_and_does_not_mutate_input() -> None:
    first_rules = {
        "dealer_hits_soft_17": True,
        "blackjack_payout": "6:5",
        "nested": {"values": [1, 2, 3]},
    }
    second_rules = {
        "nested": {"values": [1, 2, 3]},
        "blackjack_payout": "6:5",
        "dealer_hits_soft_17": True,
    }
    original = {
        "dealer_hits_soft_17": True,
        "blackjack_payout": "6:5",
        "nested": {"values": [1, 2, 3]},
    }

    assert make_machine_ev_rules_signature(first_rules) == (
        make_machine_ev_rules_signature(second_rules)
    )
    assert make_machine_ev_rules_signature(CoreRules()) == (
        make_machine_ev_rules_signature(CoreRules())
    )
    assert first_rules == original


def test_aggregate_machine_ev_state_evaluations() -> None:
    result = aggregate_machine_ev_state_evaluations(
        ((0.25, 1.0), (0.75, -1.0))
    )

    assert result == pytest.approx(-0.5)


@pytest.mark.parametrize(
    "weighted_items",
    [
        ((math.nan, 1.0),),
        ((0.5, math.inf),),
        ((-0.1, 1.0),),
    ],
)
def test_aggregate_machine_ev_rejects_invalid_values(
    weighted_items: tuple[tuple[float, float], ...],
) -> None:
    with pytest.raises(ValueError, match="finite|non-negative"):
        aggregate_machine_ev_state_evaluations(weighted_items)


def test_precision_mode_remains_exact_observable_enumeration() -> None:
    config = MachineEvConfig()

    assert config.precision_mode == (
        "exact_observable_initial_states_with_hybrid_decision"
    )
    assert "sampled" not in config.precision_mode
    assert "partial" not in config.precision_mode


def test_evaluator_uses_probability_weighted_state_ev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = (
        _state(player_cards=("2", "10"), dealer_upcard="6", probability=0.25),
        _state(player_cards=("A", "10"), dealer_upcard="10", probability=0.75),
    )
    state_evs = {
        states[0].canonical_key: 1.0,
        states[1].canonical_key: -0.5,
    }

    monkeypatch.setattr(
        evaluator_module,
        "enumerate_observable_initial_states",
        lambda shoe_counts, config: states,
    )

    def fake_evaluate(
        state: MachineEvInitialState,
        machine_input: MachineEvInput,
        config: MachineEvConfig,
    ) -> MachineEvStateEvaluation:
        return MachineEvStateEvaluation(
            player_cards=state.player_cards,
            dealer_upcard=state.dealer_upcard,
            probability=state.probability,
            best_action="stand",
            state_ev=state_evs[state.canonical_key],
            action_evs=(("stand", state_evs[state.canonical_key]),),
        )

    monkeypatch.setattr(
        evaluator_module,
        "evaluate_initial_state_with_decision_engine",
        fake_evaluate,
    )

    result = evaluate_machine_ev_pre_round(MachineEvInput(number_of_decks=1))

    assert result.raw_ev_per_unit == pytest.approx(0.25 * 1.0 + 0.75 * -0.5)
    assert result.metrics.states_evaluated == 2


def test_positive_edge_minimum_bet_within_risk_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_machine_ev_edge(monkeypatch, 0.05)

    result = evaluate_machine_ev_pre_round(
        MachineEvInput(
            number_of_decks=1,
            bankroll=1000,
            minimum_bet=10,
        )
    )

    assert result.summary.estimated_next_hand_edge == pytest.approx(0.05)
    assert result.summary.risk_if_minimum_bet is not None
    assert result.summary.risk_if_minimum_bet <= 0.05
    assert math.isfinite(
        result.summary.minimum_bankroll_required_for_minimum_bet
    )
    assert result.summary.recommendation_status == (
        "machine_ev_minimum_bet_within_risk_limit"
    )


def test_positive_edge_minimum_bet_exceeds_risk_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_machine_ev_edge(monkeypatch, 0.0011)

    result = evaluate_machine_ev_pre_round(
        MachineEvInput(
            number_of_decks=1,
            bankroll=1000,
            minimum_bet=10,
        )
    )

    assert result.summary.risk_if_minimum_bet is not None
    assert result.summary.risk_if_minimum_bet > 0.05
    assert result.summary.minimum_bankroll_required_for_minimum_bet > 1000
    assert result.summary.recommendation_status == (
        "machine_ev_minimum_bet_exceeds_risk_limit"
    )
    assert "vantagem estimada é positiva" in result.summary.recommendation_text
    assert "excede o limite" in result.summary.recommendation_text


@pytest.mark.parametrize("edge", [0.0, -0.01])
def test_non_positive_edge_has_maximum_risk(
    monkeypatch: pytest.MonkeyPatch,
    edge: float,
) -> None:
    _mock_machine_ev_edge(monkeypatch, edge)

    result = evaluate_machine_ev_pre_round(
        MachineEvInput(
            number_of_decks=1,
            bankroll=1000,
            minimum_bet=10,
        )
    )

    assert result.summary.risk_if_minimum_bet == 1.0
    assert result.summary.minimum_bankroll_required_for_minimum_bet is None
    assert result.summary.recommendation_status == "machine_ev_non_positive_edge"
    assert "não há banca finita" in result.summary.recommendation_text
    assert "garant" not in result.summary.recommendation_text.lower()


def test_missing_bankroll_still_calculates_required_bankroll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_machine_ev_edge(monkeypatch, 0.05)

    result = evaluate_machine_ev_pre_round(
        MachineEvInput(
            number_of_decks=1,
            bankroll=None,
            minimum_bet=10,
        )
    )

    assert result.summary.risk_if_minimum_bet is None
    assert math.isfinite(
        result.summary.minimum_bankroll_required_for_minimum_bet
    )
    assert result.summary.recommendation_status == "machine_ev_missing_wager_inputs"


def test_missing_minimum_bet_has_no_risk_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_machine_ev_edge(monkeypatch, 0.05)

    result = evaluate_machine_ev_pre_round(
        MachineEvInput(
            number_of_decks=1,
            bankroll=1000,
            minimum_bet=None,
        )
    )

    assert result.summary.risk_if_minimum_bet is None
    assert result.summary.minimum_bankroll_required_for_minimum_bet is None
    assert result.summary.recommendation_status == "machine_ev_missing_wager_inputs"


@pytest.mark.parametrize("minimum_bet", [0, -1, math.nan, math.inf])
def test_invalid_minimum_bet_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
    minimum_bet: float,
) -> None:
    _mock_machine_ev_edge(monkeypatch, 0.05)

    with pytest.raises(ValueError, match="minimum_bet must be a positive finite number"):
        evaluate_machine_ev_pre_round(
            MachineEvInput(
                number_of_decks=1,
                bankroll=1000,
                minimum_bet=minimum_bet,
            )
        )


@pytest.mark.parametrize("bankroll", [0, -1, math.nan, math.inf])
def test_invalid_bankroll_returns_objective_status(
    monkeypatch: pytest.MonkeyPatch,
    bankroll: float,
) -> None:
    _mock_machine_ev_edge(monkeypatch, 0.05)

    result = evaluate_machine_ev_pre_round(
        MachineEvInput(
            number_of_decks=1,
            bankroll=bankroll,
            minimum_bet=10,
        )
    )

    assert result.summary.risk_if_minimum_bet is None
    assert result.summary.minimum_bankroll_required_for_minimum_bet is None
    assert result.summary.recommendation_status == "machine_ev_invalid_bankroll"


def test_diagnostics_use_custom_variance_fallback() -> None:
    default = calculate_machine_ev_minimum_bet_diagnostics(
        estimated_next_hand_edge=0.05,
        bankroll=1000,
        minimum_bet=10,
        config=MachineEvConfig(),
    )
    custom = calculate_machine_ev_minimum_bet_diagnostics(
        estimated_next_hand_edge=0.05,
        bankroll=1000,
        minimum_bet=10,
        config=MachineEvConfig(variance_per_unit_fallback=2.6),
    )

    assert default.variance_per_unit == 1.3
    assert custom.variance_per_unit == 2.6
    assert custom.risk_if_minimum_bet > default.risk_if_minimum_bet
    assert (
        custom.minimum_bankroll_required_for_minimum_bet
        > default.minimum_bankroll_required_for_minimum_bet
    )


def test_not_evaluated_diagnostics_have_no_wager_values() -> None:
    diagnostics = calculate_machine_ev_minimum_bet_diagnostics(
        estimated_next_hand_edge=None,
        bankroll=1000,
        minimum_bet=10,
        config=MachineEvConfig(),
    )

    assert diagnostics.risk_if_minimum_bet is None
    assert diagnostics.minimum_bankroll_required_for_minimum_bet is None
    assert diagnostics.minimum_bet_exceeds_risk_cap is None
    assert diagnostics.diagnostic_status == "not_evaluated"


def test_diagnostics_use_custom_risk_limit() -> None:
    default = calculate_machine_ev_minimum_bet_diagnostics(
        estimated_next_hand_edge=0.016,
        bankroll=1000,
        minimum_bet=10,
        config=MachineEvConfig(),
    )
    custom = calculate_machine_ev_minimum_bet_diagnostics(
        estimated_next_hand_edge=0.016,
        bankroll=1000,
        minimum_bet=10,
        config=MachineEvConfig(risk_of_ruin_limit=0.10),
    )

    assert default.diagnostic_status == "minimum_bet_exceeds_risk_limit"
    assert default.minimum_bet_exceeds_risk_cap is True
    assert custom.diagnostic_status == "minimum_bet_within_risk_limit"
    assert custom.minimum_bet_exceeds_risk_cap is False
    assert custom.risk_of_ruin_limit == 0.10


def test_machine_ev_summary_stays_minimal() -> None:
    field_names = {field.name for field in fields(MachineEvPublicSummary)}

    assert field_names.isdisjoint(
        {
            "running_count",
            "true_count",
            "betting_true_count",
            "ace_side_count",
            "scaled_running_count",
            "suggested_units",
            "suggested_amount",
            "states_evaluated",
            "cache_hits",
        }
    )


def test_adapter_propagates_mode_rules_and_exact_shoe_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = next(
        item
        for item in evaluator_module.enumerate_observable_initial_states(
            build_machine_ev_shoe_counts(1, ("2",)),
        )
        if item.player_cards == ("A", "10")
    )
    captured: dict[str, object] = {}

    def fake_engine_run(**kwargs: object) -> tuple[tuple[str, float], ...]:
        captured.update(kwargs)
        return (("stand", 0.25),)

    monkeypatch.setattr(evaluator_module, "_evaluate_action_evs", fake_engine_run)
    machine_input = MachineEvInput(
        number_of_decks=1,
        seen_cards=("2",),
        rules={
            "dealer_hits_soft_17": True,
            "blackjack_payout": "6:5",
            "surrender_allowed": True,
        },
    )
    config = MachineEvConfig(decision_engine_mode="hybrid")

    evaluation = evaluator_module.evaluate_initial_state_with_decision_engine(
        state,
        machine_input,
        config,
    )

    core_state = captured["state"]
    active_rules = captured["active_rules"]
    assert captured["mode"] == "hybrid"
    assert core_state.deck_counts == tuple(count for _, count in state.shoe_after)
    assert core_state.seen_ranks == (1,)
    assert core_state.rules.dealer_hits_soft_17 is True
    assert core_state.rules.blackjack_payout == "6:5"
    assert active_rules.surrender_allowed is True
    assert evaluation.state_ev == 0.25


def test_evaluator_does_not_mutate_input() -> None:
    seen_cards = ("2", "3", "4")
    rules = {"dealer_hits_soft_17": True}
    machine_input = MachineEvInput(
        number_of_decks=1,
        seen_cards=seen_cards,
        rules=rules,
    )
    original_rules = rules.copy()

    evaluate_machine_ev_pre_round(machine_input)

    assert machine_input.seen_cards == seen_cards
    assert rules == original_rules


def test_machine_ev_models_do_not_reveal_dealer_hole_card() -> None:
    result_fields = {field.name for field in fields(MachineEvResult)}
    evaluation_fields = {field.name for field in fields(MachineEvStateEvaluation)}

    assert "dealer_hole_card" not in result_fields
    assert "dealer_hole_card" not in evaluation_fields


def test_neutral_six_deck_shoe_returns_plausible_finite_ev() -> None:
    result = evaluate_machine_ev_pre_round(MachineEvInput(number_of_decks=6))

    assert math.isfinite(result.raw_ev_per_unit)
    assert -0.20 <= result.raw_ev_per_unit <= 0.20


def test_rich_and_poor_shoes_return_finite_values() -> None:
    rich_seen = tuple(
        rank
        for rank in ("2", "3", "4", "5", "6")
        for _ in range(4)
    )
    poor_seen = ("A",) * 4 + ("9",) * 4 + ("10",) * 16

    rich = evaluate_machine_ev_pre_round(
        MachineEvInput(number_of_decks=1, seen_cards=rich_seen)
    )
    poor = evaluate_machine_ev_pre_round(
        MachineEvInput(number_of_decks=1, seen_cards=poor_seen)
    )

    assert math.isfinite(rich.raw_ev_per_unit)
    assert math.isfinite(poor.raw_ev_per_unit)


def test_almost_consumed_shoe_returns_finite_result_or_clear_error() -> None:
    full_shoe = _full_shoe_cards(1)
    cards_left = ["A", "2", "3"]
    seen_cards = list(full_shoe)
    for card in cards_left:
        seen_cards.remove(card)

    with pytest.raises(ValueError, match="Unable to evaluate observable state"):
        evaluate_machine_ev_pre_round(
            MachineEvInput(number_of_decks=1, seen_cards=tuple(seen_cards))
        )


def test_fewer_than_three_cards_raises_clear_error() -> None:
    full_shoe = _full_shoe_cards(1)
    cards_left = ["A", "10"]
    seen_cards = list(full_shoe)
    for card in cards_left:
        seen_cards.remove(card)

    with pytest.raises(ValueError, match="At least 3 cards"):
        evaluate_machine_ev_pre_round(
            MachineEvInput(number_of_decks=1, seen_cards=tuple(seen_cards))
        )


def test_state_breakdown_is_optional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = (
        _state(player_cards=("8", "10"), dealer_upcard="6", probability=1.0),
    )
    monkeypatch.setattr(
        evaluator_module,
        "enumerate_observable_initial_states",
        lambda shoe_counts, config: states,
    )
    monkeypatch.setattr(
        evaluator_module,
        "evaluate_initial_state_with_decision_engine",
        lambda state, machine_input, config: MachineEvStateEvaluation(
            player_cards=state.player_cards,
            dealer_upcard=state.dealer_upcard,
            probability=state.probability,
            best_action="stand",
            state_ev=0.1,
            action_evs=(("stand", 0.1),),
        ),
    )

    without_breakdown = evaluate_machine_ev_pre_round(
        MachineEvInput(number_of_decks=1),
        MachineEvConfig(include_state_breakdown=False),
    )
    with_breakdown = evaluate_machine_ev_pre_round(
        MachineEvInput(number_of_decks=1),
        MachineEvConfig(include_state_breakdown=True),
    )

    assert without_breakdown.state_evaluations is None
    assert with_breakdown.state_evaluations is not None
    assert len(with_breakdown.state_evaluations) == 1


def test_evaluator_uses_no_http_or_human_counting_systems() -> None:
    source = inspect.getsource(evaluator_module)

    assert "TestClient" not in source
    assert "requests" not in source
    assert "HI_LO" not in source
    assert "HI_OPT_II" not in source
    assert "WONG_HALVES" not in source
    assert "engine_core.counting" not in source
