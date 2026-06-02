from __future__ import annotations

from dataclasses import dataclass

from blackjack_risk_engine.decisions import Decision


@dataclass(frozen=True, slots=True)
class ExpectedValue:
    decision: Decision
    value: float
    simulations: int = 0


def best_expected_value(values: list[ExpectedValue]) -> ExpectedValue:
    if not values:
        raise ValueError("values must not be empty")
    return max(values, key=lambda item: item.value)
