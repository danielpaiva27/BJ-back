from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RiskProfile:
    expected_value: float
    standard_deviation: float
    loss_probability: float
    ruin_probability: float | None = None
