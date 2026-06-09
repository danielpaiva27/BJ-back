"""Internal contracts for the future composition-based pre-round Machine EV."""

from blackjack_risk_engine.engine_core.pre_round.machine_ev.config import (
    MachineEvConfig,
    create_default_machine_ev_config,
)
from blackjack_risk_engine.engine_core.pre_round.machine_ev.evaluator import (
    aggregate_machine_ev_state_evaluations,
    build_machine_ev_shoe_counts,
    calculate_machine_ev_minimum_bet_diagnostics,
    evaluate_initial_state_with_decision_engine,
    evaluate_machine_ev_pre_round,
    make_machine_ev_rules_signature,
)
from blackjack_risk_engine.engine_core.pre_round.machine_ev.models import (
    MachineEvInput,
    MachineEvInitialState,
    MachineEvInternalMetrics,
    MachineEvMinimumBetDiagnostics,
    MachineEvPublicSummary,
    MachineEvResult,
    MachineEvStateEvaluation,
    create_not_evaluated_machine_ev_result,
)
from blackjack_risk_engine.engine_core.pre_round.machine_ev.predeal_enumerator import (
    canonicalize_player_cards,
    enumerate_observable_initial_states,
    make_initial_state_key,
    make_shoe_signature,
)


__all__ = [
    "MachineEvConfig",
    "MachineEvInput",
    "MachineEvInitialState",
    "MachineEvInternalMetrics",
    "MachineEvMinimumBetDiagnostics",
    "MachineEvPublicSummary",
    "MachineEvResult",
    "MachineEvStateEvaluation",
    "aggregate_machine_ev_state_evaluations",
    "build_machine_ev_shoe_counts",
    "calculate_machine_ev_minimum_bet_diagnostics",
    "canonicalize_player_cards",
    "create_default_machine_ev_config",
    "create_not_evaluated_machine_ev_result",
    "enumerate_observable_initial_states",
    "evaluate_initial_state_with_decision_engine",
    "evaluate_machine_ev_pre_round",
    "make_initial_state_key",
    "make_machine_ev_rules_signature",
    "make_shoe_signature",
]
