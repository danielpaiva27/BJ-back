from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class MachineEvConfig:
    enabled: bool = True
    decision_engine_mode: str = "hybrid"
    max_duration_ms: int = 1500
    use_cache: bool = True
    include_debug_metrics: bool = False
    include_state_breakdown: bool = False
    variance_per_unit_fallback: float = 1.3
    risk_of_ruin_limit: float = 0.05
    precision_mode: str = (
        "exact_observable_initial_states_with_deterministic_public_actions"
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.decision_engine_mode, str)
            or not self.decision_engine_mode.strip()
        ):
            raise ValueError("decision_engine_mode must be a non-empty string")
        if (
            not isinstance(self.precision_mode, str)
            or not self.precision_mode.strip()
        ):
            raise ValueError("precision_mode must be a non-empty string")
        if (
            isinstance(self.max_duration_ms, bool)
            or not isinstance(self.max_duration_ms, int)
            or self.max_duration_ms <= 0
        ):
            raise ValueError("max_duration_ms must be a positive integer")
        if (
            not isinstance(self.variance_per_unit_fallback, (int, float))
            or isinstance(self.variance_per_unit_fallback, bool)
            or not isfinite(self.variance_per_unit_fallback)
            or self.variance_per_unit_fallback <= 0
        ):
            raise ValueError("variance_per_unit_fallback must be greater than zero")
        if (
            not isinstance(self.risk_of_ruin_limit, (int, float))
            or isinstance(self.risk_of_ruin_limit, bool)
            or not isfinite(self.risk_of_ruin_limit)
            or not 0 < self.risk_of_ruin_limit < 1
        ):
            raise ValueError("risk_of_ruin_limit must be greater than 0 and less than 1")


def create_default_machine_ev_config() -> MachineEvConfig:
    return MachineEvConfig()
