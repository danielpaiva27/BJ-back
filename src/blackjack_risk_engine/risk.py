from __future__ import annotations

"""Risk and bet sizing helpers.

The initial bet spread is intentionally simple:
- conservative: 1-4 units, capped at 1% of bankroll.
- moderate: 1-6 units, capped at 3% of bankroll.
- aggressive: 1-10 units, capped at 5% of bankroll.

This is an academic/simulation model, not a profit guarantee.
"""

from dataclasses import dataclass
from typing import Literal


BettingRiskProfile = Literal["conservative", "moderate", "aggressive"]


@dataclass(frozen=True, slots=True)
class RiskProfile:
    expected_value: float
    standard_deviation: float
    loss_probability: float
    ruin_probability: float | None = None


@dataclass(frozen=True, slots=True)
class BettingSuggestion:
    suggested_bet: float
    bet_units: float
    risk_profile: BettingRiskProfile
    explanation: str


@dataclass(frozen=True, slots=True)
class _BetSpreadProfile:
    max_bankroll_fraction: float
    units_by_true_count: tuple[tuple[float, int], ...]


BET_SPREADS: dict[BettingRiskProfile, _BetSpreadProfile] = {
    "conservative": _BetSpreadProfile(
        max_bankroll_fraction=0.01,
        units_by_true_count=((1, 1), (2, 2), (4, 3), (6, 4)),
    ),
    "moderate": _BetSpreadProfile(
        max_bankroll_fraction=0.03,
        units_by_true_count=((1, 1), (2, 2), (3, 4), (5, 6)),
    ),
    "aggressive": _BetSpreadProfile(
        max_bankroll_fraction=0.05,
        units_by_true_count=((1, 1), (2, 3), (3, 6), (5, 10)),
    ),
}


def suggest_bet(
    true_count: float,
    minimum_bet: float,
    bankroll: float,
    risk_profile: BettingRiskProfile = "moderate",
) -> BettingSuggestion:
    if minimum_bet <= 0:
        raise ValueError("minimum_bet must be greater than zero")
    if bankroll <= 0:
        raise ValueError("bankroll must be greater than zero")
    if risk_profile not in BET_SPREADS:
        raise ValueError("risk_profile must be one of: conservative, moderate, aggressive")

    profile = BET_SPREADS[risk_profile]
    target_units = _units_for_true_count(true_count, profile)
    target_bet = minimum_bet * target_units
    max_allowed_bet = bankroll * profile.max_bankroll_fraction
    suggested_bet = min(target_bet, max_allowed_bet)
    bet_units = suggested_bet / minimum_bet

    explanation = (
        f"Modelo academico/simulacional Hi-Lo: perfil {risk_profile} usa spread "
        f"baseado no true_count e limita a aposta a "
        f"{profile.max_bankroll_fraction:.1%} da banca. "
        "Isso nao e garantia de lucro."
    )

    return BettingSuggestion(
        suggested_bet=round(suggested_bet, 2),
        bet_units=round(bet_units, 2),
        risk_profile=risk_profile,
        explanation=explanation,
    )


def _units_for_true_count(true_count: float, profile: _BetSpreadProfile) -> int:
    units = 1
    for threshold, threshold_units in profile.units_by_true_count:
        if true_count >= threshold:
            units = threshold_units
    return units
