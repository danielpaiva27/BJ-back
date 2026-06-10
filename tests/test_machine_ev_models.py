from dataclasses import fields

import pytest

from blackjack_risk_engine.engine_core.counting import (
    HI_LO,
    HI_OPT_II,
    WONG_HALVES,
    get_count_system,
)
from blackjack_risk_engine.engine_core.pre_round.machine_ev import (
    MachineEvConfig,
    MachineEvInput,
    MachineEvInternalMetrics,
    MachineEvPublicSummary,
    MachineEvResult,
    create_default_machine_ev_config,
    create_not_evaluated_machine_ev_result,
)


def test_machine_ev_config_defaults() -> None:
    config = create_default_machine_ev_config()

    assert config.enabled is True
    assert config.decision_engine_mode == "hybrid"
    assert config.max_duration_ms > 0
    assert config.use_cache is True
    assert config.include_debug_metrics is False
    assert config.include_state_breakdown is False
    assert config.risk_of_ruin_limit == 0.05
    assert config.variance_per_unit_fallback == 1.3
    assert config.precision_mode == (
        "exact_observable_initial_states_with_deterministic_public_actions"
    )


def test_machine_ev_input_is_structural_only() -> None:
    input_data = MachineEvInput(
        number_of_decks=6,
        seen_cards=("A", "10"),
        bankroll=1000,
        minimum_bet=10,
        rules={"dealer_hits_soft_17": False},
    )

    assert input_data.number_of_decks == 6
    assert input_data.seen_cards == ("A", "10")
    assert input_data.rules == {"dealer_hits_soft_17": False}


def test_machine_ev_result_model_defaults_to_not_evaluated_contract() -> None:
    result = MachineEvResult()

    assert isinstance(result.summary, MachineEvPublicSummary)
    assert isinstance(result.metrics, MachineEvInternalMetrics)
    assert result.config is None
    assert result.raw_ev_per_unit is None
    assert result.variance_per_unit is None
    assert result.state_evaluations is None


@pytest.mark.parametrize("max_duration_ms", [0, -1])
def test_machine_ev_config_rejects_invalid_duration(max_duration_ms: int) -> None:
    with pytest.raises(ValueError, match="max_duration_ms"):
        MachineEvConfig(max_duration_ms=max_duration_ms)


@pytest.mark.parametrize("risk_of_ruin_limit", [0, -0.1, 1, 1.1])
def test_machine_ev_config_rejects_invalid_risk_limit(
    risk_of_ruin_limit: float,
) -> None:
    with pytest.raises(ValueError, match="risk_of_ruin_limit"):
        MachineEvConfig(risk_of_ruin_limit=risk_of_ruin_limit)


@pytest.mark.parametrize("variance_per_unit_fallback", [0, -1.0])
def test_machine_ev_config_rejects_invalid_variance(
    variance_per_unit_fallback: float,
) -> None:
    with pytest.raises(ValueError, match="variance_per_unit_fallback"):
        MachineEvConfig(variance_per_unit_fallback=variance_per_unit_fallback)


@pytest.mark.parametrize("decision_engine_mode", ["", "   "])
def test_machine_ev_config_rejects_empty_engine_mode(
    decision_engine_mode: str,
) -> None:
    with pytest.raises(ValueError, match="decision_engine_mode"):
        MachineEvConfig(decision_engine_mode=decision_engine_mode)


def test_create_not_evaluated_machine_ev_result() -> None:
    config = MachineEvConfig()
    result = create_not_evaluated_machine_ev_result(config)
    summary = result.summary

    assert result.config is config
    assert summary.model_id == "machine_ev"
    assert summary.label == "Machine EV"
    assert summary.model_type == "composition_ev"
    assert summary.is_human_replicable is False
    assert summary.estimated_next_hand_edge is None
    assert summary.risk_if_minimum_bet is None
    assert summary.minimum_bankroll_required_for_minimum_bet is None
    assert summary.recommendation_status == "not_evaluated"
    assert result.raw_ev_per_unit is None
    assert result.variance_per_unit is None


def test_machine_ev_summary_has_no_human_counting_fields() -> None:
    field_names = {field.name for field in fields(MachineEvPublicSummary)}

    assert field_names.isdisjoint(
        {
            "running_count",
            "true_count",
            "betting_true_count",
            "ace_side_count",
            "scaled_running_count",
        }
    )


def test_importing_machine_ev_does_not_change_human_counting_systems() -> None:
    assert get_count_system("hi_lo") is HI_LO
    assert get_count_system("hi_opt_ii") is HI_OPT_II
    assert get_count_system("wong_halves") is WONG_HALVES


def test_not_evaluated_factory_is_pure_and_has_zero_work_metrics() -> None:
    first = create_not_evaluated_machine_ev_result()
    second = create_not_evaluated_machine_ev_result()

    assert first == second
    assert first is not second
    assert first.summary is not second.summary
    assert first.metrics.states_evaluated == 0
    assert first.metrics.cache_hits == 0
    assert first.metrics.cache_misses == 0
    assert first.metrics.duration_ms is None
    assert first.metrics.timed_out is False
    assert first.metrics.warnings == ()
