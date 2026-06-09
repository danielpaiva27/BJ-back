from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import TypeAlias

from blackjack_risk_engine.engine_core.cards import RANK_STRINGS, RANK_TO_INDEX
from blackjack_risk_engine.engine_core.pre_round.machine_ev.config import (
    MachineEvConfig,
)
from blackjack_risk_engine.engine_core.pre_round.machine_ev.constants import (
    DEFAULT_MACHINE_EV_STATUS,
    DEFAULT_MACHINE_EV_TEXT,
    MACHINE_EV_HUMAN_REPLICABLE,
    MACHINE_EV_LABEL,
    MACHINE_EV_MODEL_ID,
    MACHINE_EV_MODEL_TYPE,
)


MachineEvInitialStateKey: TypeAlias = tuple[
    tuple[str, str],
    str,
    tuple[int, ...],
]


@dataclass(frozen=True, slots=True)
class MachineEvInput:
    number_of_decks: int
    seen_cards: tuple[str, ...] = ()
    bankroll: float | None = None
    minimum_bet: float | None = None
    rules: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class MachineEvInitialState:
    player_cards: tuple[str, str]
    dealer_upcard: str
    shoe_after: tuple[tuple[str, int], ...]
    probability: float
    canonical_key: MachineEvInitialStateKey
    path_count: int = 1

    def __post_init__(self) -> None:
        if len(self.player_cards) != 2 or any(
            card not in RANK_TO_INDEX for card in self.player_cards
        ):
            raise ValueError("player_cards must contain exactly two normalized ranks")
        if RANK_TO_INDEX[self.player_cards[0]] > RANK_TO_INDEX[self.player_cards[1]]:
            raise ValueError("player_cards must use canonical rank order")
        if self.dealer_upcard not in RANK_TO_INDEX:
            raise ValueError("dealer_upcard must be a normalized rank")

        shoe_ranks = tuple(rank for rank, _ in self.shoe_after)
        if shoe_ranks != RANK_STRINGS:
            raise ValueError("shoe_after must contain all ranks in canonical order")
        if any(
            isinstance(count, bool) or not isinstance(count, int) or count < 0
            for _, count in self.shoe_after
        ):
            raise ValueError("shoe_after must contain non-negative integer counts")

        if (
            isinstance(self.probability, bool)
            or not isinstance(self.probability, (int, float))
            or not isfinite(self.probability)
            or not 0 <= self.probability <= 1
        ):
            raise ValueError("probability must be finite and between 0 and 1")
        if (
            isinstance(self.path_count, bool)
            or not isinstance(self.path_count, int)
            or self.path_count <= 0
        ):
            raise ValueError("path_count must be a positive integer")

        expected_key = (
            self.player_cards,
            self.dealer_upcard,
            tuple(count for _, count in self.shoe_after),
        )
        if self.canonical_key != expected_key:
            raise ValueError("canonical_key does not match the observable state")


@dataclass(frozen=True, slots=True)
class MachineEvStateEvaluation:
    player_cards: tuple[str, str]
    dealer_upcard: str
    probability: float
    best_action: str | None
    state_ev: float
    action_evs: tuple[tuple[str, float], ...] = ()
    warning: str | None = None

    def __post_init__(self) -> None:
        if len(self.player_cards) != 2 or any(
            card not in RANK_TO_INDEX for card in self.player_cards
        ):
            raise ValueError("player_cards must contain exactly two normalized ranks")
        if RANK_TO_INDEX[self.player_cards[0]] > RANK_TO_INDEX[self.player_cards[1]]:
            raise ValueError("player_cards must use canonical rank order")
        if self.dealer_upcard not in RANK_TO_INDEX:
            raise ValueError("dealer_upcard must be a normalized rank")
        if (
            isinstance(self.probability, bool)
            or not isinstance(self.probability, (int, float))
            or not isfinite(self.probability)
            or not 0 <= self.probability <= 1
        ):
            raise ValueError("probability must be finite and between 0 and 1")
        if (
            isinstance(self.state_ev, bool)
            or not isinstance(self.state_ev, (int, float))
            or not isfinite(self.state_ev)
        ):
            raise ValueError("state_ev must be finite")
        if any(
            not isinstance(action, str)
            or not action
            or isinstance(ev, bool)
            or not isinstance(ev, (int, float))
            or not isfinite(ev)
            for action, ev in self.action_evs
        ):
            raise ValueError("action_evs must contain action names and finite EV values")


@dataclass(frozen=True, slots=True)
class MachineEvMinimumBetDiagnostics:
    risk_if_minimum_bet: float | None
    minimum_bankroll_required_for_minimum_bet: float | None
    minimum_bet_exceeds_risk_cap: bool | None
    risk_of_ruin_limit: float
    variance_per_unit: float
    diagnostic_status: str
    diagnostic_text: str

    def __post_init__(self) -> None:
        if self.risk_if_minimum_bet is not None and (
            isinstance(self.risk_if_minimum_bet, bool)
            or not isinstance(self.risk_if_minimum_bet, (int, float))
            or not isfinite(self.risk_if_minimum_bet)
            or not 0 <= self.risk_if_minimum_bet <= 1
        ):
            raise ValueError("risk_if_minimum_bet must be between 0 and 1")
        if self.minimum_bankroll_required_for_minimum_bet is not None and (
            isinstance(
                self.minimum_bankroll_required_for_minimum_bet,
                bool,
            )
            or not isinstance(
                self.minimum_bankroll_required_for_minimum_bet,
                (int, float),
            )
            or not isfinite(
                self.minimum_bankroll_required_for_minimum_bet,
            )
            or self.minimum_bankroll_required_for_minimum_bet < 0
        ):
            raise ValueError(
                "minimum_bankroll_required_for_minimum_bet must be non-negative"
            )
        if (
            self.minimum_bet_exceeds_risk_cap is not None
            and not isinstance(self.minimum_bet_exceeds_risk_cap, bool)
        ):
            raise ValueError(
                "minimum_bet_exceeds_risk_cap must be a boolean or None"
            )
        if (
            isinstance(self.risk_of_ruin_limit, bool)
            or not isinstance(self.risk_of_ruin_limit, (int, float))
            or not isfinite(self.risk_of_ruin_limit)
            or not 0 < self.risk_of_ruin_limit < 1
        ):
            raise ValueError("risk_of_ruin_limit must be between 0 and 1")
        if (
            isinstance(self.variance_per_unit, bool)
            or not isinstance(self.variance_per_unit, (int, float))
            or not isfinite(self.variance_per_unit)
            or self.variance_per_unit <= 0
        ):
            raise ValueError("variance_per_unit must be greater than zero")
        if not self.diagnostic_status:
            raise ValueError("diagnostic_status must not be empty")
        if not self.diagnostic_text:
            raise ValueError("diagnostic_text must not be empty")


@dataclass(frozen=True, slots=True)
class MachineEvPublicSummary:
    model_id: str = MACHINE_EV_MODEL_ID
    label: str = MACHINE_EV_LABEL
    model_type: str = MACHINE_EV_MODEL_TYPE
    estimated_next_hand_edge: float | None = None
    risk_if_minimum_bet: float | None = None
    minimum_bankroll_required_for_minimum_bet: float | None = None
    recommendation_status: str = DEFAULT_MACHINE_EV_STATUS
    recommendation_text: str = DEFAULT_MACHINE_EV_TEXT
    is_human_replicable: bool = MACHINE_EV_HUMAN_REPLICABLE


@dataclass(frozen=True, slots=True)
class MachineEvInternalMetrics:
    states_evaluated: int = 0
    duration_ms: float | None = None
    cache_hits: int = 0
    cache_misses: int = 0
    timed_out: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MachineEvResult:
    summary: MachineEvPublicSummary = field(default_factory=MachineEvPublicSummary)
    metrics: MachineEvInternalMetrics = field(default_factory=MachineEvInternalMetrics)
    config: MachineEvConfig | None = None
    raw_ev_per_unit: float | None = None
    variance_per_unit: float | None = None
    state_evaluations: tuple[MachineEvStateEvaluation, ...] | None = None


def create_not_evaluated_machine_ev_result(
    config: MachineEvConfig | None = None,
) -> MachineEvResult:
    return MachineEvResult(config=config)
