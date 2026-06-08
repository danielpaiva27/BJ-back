from __future__ import annotations

import math
from fractions import Fraction
from numbers import Real
from typing import TypeAlias


POLICY_ID = "risk_capped_growth"
POLICY_LABEL = "Crescimento com risco de quebra limitado"
POLICY_DESCRIPTION = (
    "Politica que escolhe a maior exposicao simulada justificada pela "
    "vantagem estimada, limitada por um risco de quebra aproximado de no "
    "maximo 5%."
)

RISK_MODEL = "approx_exponential_gambler_ruin"
VARIANCE_PER_UNIT = 1.3
RISK_OF_RUIN_LIMIT = 0.05
MAX_SINGLE_ROUND_EXPOSURE = 0.05

# Compatibility aliases. Quarter-Kelly is no longer used by the policy.
SAFETY_KELLY_FRACTION = 0.25
MAX_BANKROLL_EXPOSURE = MAX_SINGLE_ROUND_EXPOSURE

BankrollRecommendation: TypeAlias = dict[
    str,
    str | bool | int | float | None | list[str] | dict[str, float | str],
]
PolicyInfo: TypeAlias = dict[str, str | float]

RISK_APPROXIMATION_WARNING = (
    "O risco de quebra e uma aproximacao matematica, nao uma garantia."
)

_STATUS_TEXT = {
    "observe": (
        "Sem vantagem estimada suficiente. A politica sugere observar e "
        "continuar registrando cartas."
    ),
    "marginal_observe": (
        "A vantagem estimada e positiva, mas nao sustenta a unidade minima "
        "dentro do limite aproximado de risco de quebra."
    ),
    "positive_edge_minimum_bet_exceeds_risk_cap": (
        "Ha vantagem estimada, mas a menor aposta possivel ultrapassa o "
        "limite aproximado de risco de quebra de 5% para a banca atual."
    ),
    "minimum_unit": (
        "Ha vantagem estimada positiva. A politica sugere a unidade minima "
        "dentro do limite aproximado de risco de quebra."
    ),
    "favorable_risk_capped": (
        "Ha vantagem estimada positiva. A sugestao maximiza a exposicao "
        "simulada dentro do limite aproximado de 5% de risco de quebra."
    ),
    "invalid_bankroll": "Banca simulada invalida.",
    "invalid_minimum_bet": "Unidade minima invalida.",
    "insufficient_bankroll": "Banca simulada insuficiente para a unidade minima.",
}


def estimate_risk_of_ruin(
    bankroll: float,
    bet_amount: float,
    estimated_player_edge: float,
    variance_per_unit: float = VARIANCE_PER_UNIT,
) -> float:
    """Estimate risk of ruin with a positive-drift exponential model.

    The approximation uses edge and variance per unit for a theoretical
    random walk. It is not a guarantee and does not model every casino rule,
    table limit, bet sequence, estimation error, or human behavior.
    """

    bankroll_value = _require_finite_number(bankroll, "bankroll")
    bet_value = _require_finite_number(bet_amount, "bet_amount")
    edge = _require_finite_number(
        estimated_player_edge,
        "estimated_player_edge",
    )
    variance = _require_positive_finite_number(
        variance_per_unit,
        "variance_per_unit",
    )

    if bet_value <= 0:
        return 0.0
    if bankroll_value <= 0 or edge <= 0:
        return 1.0

    exponent = (-2.0 * edge * bankroll_value) / (variance * bet_value)
    try:
        risk = math.exp(exponent)
    except OverflowError:
        risk = 1.0 if exponent > 0 else 0.0

    if not math.isfinite(risk):
        raise ValueError("estimated risk of ruin must be finite")
    return min(1.0, max(0.0, risk))


def calculate_max_bet_for_risk_limit(
    bankroll: float,
    estimated_player_edge: float,
    risk_of_ruin_limit: float = RISK_OF_RUIN_LIMIT,
    variance_per_unit: float = VARIANCE_PER_UNIT,
) -> float:
    """Return the largest theoretical bet allowed by the risk approximation."""

    bankroll_value = _require_finite_number(bankroll, "bankroll")
    edge = _require_finite_number(
        estimated_player_edge,
        "estimated_player_edge",
    )
    risk_limit = _require_finite_number(
        risk_of_ruin_limit,
        "risk_of_ruin_limit",
    )
    variance = _require_positive_finite_number(
        variance_per_unit,
        "variance_per_unit",
    )

    if risk_limit <= 0 or risk_limit >= 1:
        raise ValueError("risk_of_ruin_limit must be greater than 0 and less than 1")
    if bankroll_value <= 0 or edge <= 0:
        return 0.0

    denominator = variance * math.log(1.0 / risk_limit)
    max_bet = (2.0 * edge * bankroll_value) / denominator
    if not math.isfinite(max_bet):
        raise ValueError("maximum bet allowed by risk limit must be finite")
    return max(0.0, max_bet)


def calculate_minimum_bankroll_for_bet_at_risk_limit(
    bet_amount: float,
    estimated_player_edge: float,
    risk_of_ruin_limit: float = RISK_OF_RUIN_LIMIT,
    variance_per_unit: float = VARIANCE_PER_UNIT,
) -> float | None:
    """Return bankroll required to keep a fixed bet within the risk limit."""

    bet_value = _require_finite_number(bet_amount, "bet_amount")
    edge = _require_finite_number(
        estimated_player_edge,
        "estimated_player_edge",
    )
    risk_limit = _require_finite_number(
        risk_of_ruin_limit,
        "risk_of_ruin_limit",
    )
    variance = _require_positive_finite_number(
        variance_per_unit,
        "variance_per_unit",
    )

    if risk_limit <= 0 or risk_limit >= 1:
        raise ValueError("risk_of_ruin_limit must be greater than 0 and less than 1")
    if bet_value <= 0 or edge <= 0:
        return None

    bankroll_required = (
        variance
        * bet_value
        * math.log(1.0 / risk_limit)
        / (2.0 * edge)
    )
    if not math.isfinite(bankroll_required):
        return None
    return max(0.0, bankroll_required)


def suggest_bankroll_exposure(
    bankroll: float,
    minimum_bet: float,
    estimated_player_edge: float,
    cards_remaining: int | None = None,
    system_id: str | None = None,
    risk_of_ruin_limit: float = RISK_OF_RUIN_LIMIT,
    variance_per_unit: float = VARIANCE_PER_UNIT,
    max_single_round_exposure: float = MAX_SINGLE_ROUND_EXPOSURE,
) -> BankrollRecommendation:
    """Maximize simulated exposure within approximate ruin and round caps."""

    edge = _require_finite_number(
        estimated_player_edge,
        "estimated_player_edge",
    )
    risk_limit = _validate_risk_limit(risk_of_ruin_limit)
    variance = _require_positive_finite_number(
        variance_per_unit,
        "variance_per_unit",
    )
    round_cap = _validate_exposure_fraction(max_single_round_exposure)
    _validate_cards_remaining(cards_remaining)
    warnings = [RISK_APPROXIMATION_WARNING]

    bankroll_value = _optional_finite_number(bankroll)
    minimum_bet_value = _optional_finite_number(minimum_bet)

    if bankroll_value is None or bankroll_value <= 0:
        return _build_recommendation(
            status="invalid_bankroll",
            bankroll=0.0,
            edge=edge,
            risk_limit=risk_limit,
            variance=variance,
            round_cap=round_cap,
            max_bet_by_risk=0.0,
            max_bet_by_exposure=0.0,
            warnings=warnings,
            system_id=system_id,
        )

    max_bet_by_exposure = bankroll_value * round_cap
    if minimum_bet_value is None or minimum_bet_value <= 0:
        return _build_recommendation(
            status="invalid_minimum_bet",
            bankroll=bankroll_value,
            edge=edge,
            risk_limit=risk_limit,
            variance=variance,
            round_cap=round_cap,
            max_bet_by_risk=0.0,
            max_bet_by_exposure=max_bet_by_exposure,
            warnings=warnings,
            system_id=system_id,
        )

    if bankroll_value < minimum_bet_value:
        return _build_recommendation(
            status="insufficient_bankroll",
            bankroll=bankroll_value,
            edge=edge,
            risk_limit=risk_limit,
            variance=variance,
            round_cap=round_cap,
            max_bet_by_risk=0.0,
            max_bet_by_exposure=max_bet_by_exposure,
            warnings=warnings,
            system_id=system_id,
        )

    if edge <= 0:
        return _build_recommendation(
            status="observe",
            bankroll=bankroll_value,
            edge=edge,
            risk_limit=risk_limit,
            variance=variance,
            round_cap=round_cap,
            max_bet_by_risk=0.0,
            max_bet_by_exposure=max_bet_by_exposure,
            warnings=warnings,
            system_id=system_id,
        )

    max_bet_by_risk = calculate_max_bet_for_risk_limit(
        bankroll=bankroll_value,
        estimated_player_edge=edge,
        risk_of_ruin_limit=risk_limit,
        variance_per_unit=variance,
    )
    risk_if_minimum_bet = estimate_risk_of_ruin(
        bankroll=bankroll_value,
        bet_amount=minimum_bet_value,
        estimated_player_edge=edge,
        variance_per_unit=variance,
    )
    minimum_bankroll_required_for_minimum_bet = (
        calculate_minimum_bankroll_for_bet_at_risk_limit(
            bet_amount=minimum_bet_value,
            estimated_player_edge=edge,
            risk_of_ruin_limit=risk_limit,
            variance_per_unit=variance,
        )
    )
    minimum_bet_exceeds_risk_cap = (
        edge > 0
        and max_bet_by_risk > 0
        and minimum_bet_value > max_bet_by_risk
    )
    available_amount = min(
        max_bet_by_risk,
        max_bet_by_exposure,
        bankroll_value,
    )
    suggested_units, suggested_amount = _calculate_discrete_exposure(
        available_amount,
        minimum_bet_value,
    )
    suggested_units, suggested_amount, estimated_risk = (
        _enforce_risk_limit_after_rounding(
            bankroll=bankroll_value,
            minimum_bet=minimum_bet_value,
            edge=edge,
            variance=variance,
            risk_limit=risk_limit,
            suggested_units=suggested_units,
        )
    )

    if suggested_units == 0:
        status = (
            "positive_edge_minimum_bet_exceeds_risk_cap"
            if minimum_bet_exceeds_risk_cap
            else "marginal_observe"
        )
    elif suggested_units == 1:
        status = "minimum_unit"
    else:
        status = "favorable_risk_capped"

    return _build_recommendation(
        status=status,
        bankroll=bankroll_value,
        edge=edge,
        risk_limit=risk_limit,
        variance=variance,
        round_cap=round_cap,
        max_bet_by_risk=max_bet_by_risk,
        max_bet_by_exposure=max_bet_by_exposure,
        suggested_units=suggested_units,
        suggested_amount=suggested_amount,
        estimated_risk=estimated_risk,
        risk_if_minimum_bet=risk_if_minimum_bet,
        minimum_bankroll_required_for_minimum_bet=(
            minimum_bankroll_required_for_minimum_bet
        ),
        minimum_bet_exceeds_risk_cap=minimum_bet_exceeds_risk_cap,
        warnings=warnings,
        system_id=system_id,
    )


def get_bankroll_policy_info() -> PolicyInfo:
    return {
        "policy_id": POLICY_ID,
        "policy_label": POLICY_LABEL,
        "description": POLICY_DESCRIPTION,
        "variance_per_unit": VARIANCE_PER_UNIT,
        "risk_of_ruin_limit": RISK_OF_RUIN_LIMIT,
        "max_single_round_exposure": MAX_SINGLE_ROUND_EXPOSURE,
        "max_bankroll_exposure": MAX_BANKROLL_EXPOSURE,
        "risk_model": RISK_MODEL,
    }


def _build_recommendation(
    *,
    status: str,
    bankroll: float,
    edge: float,
    risk_limit: float,
    variance: float,
    round_cap: float,
    max_bet_by_risk: float,
    max_bet_by_exposure: float,
    suggested_units: int = 0,
    suggested_amount: float = 0.0,
    estimated_risk: float = 0.0,
    risk_if_minimum_bet: float | None = None,
    minimum_bankroll_required_for_minimum_bet: float | None = None,
    minimum_bet_exceeds_risk_cap: bool = False,
    warnings: list[str],
    system_id: str | None,
) -> BankrollRecommendation:
    safe_units = max(0, suggested_units)
    safe_amount = max(0.0, suggested_amount)
    exposure_fraction = safe_amount / bankroll if bankroll > 0 else 0.0
    kelly_fraction = max(0.0, edge / variance)
    risk_limited_fraction = (
        max_bet_by_risk / bankroll
        if bankroll > 0
        else 0.0
    )
    result: BankrollRecommendation = {
        "policy_id": POLICY_ID,
        "policy_label": POLICY_LABEL,
        "should_enter": safe_units > 0,
        "suggested_units": safe_units,
        "suggested_amount": safe_amount,
        "bankroll_exposure_percent": max(0.0, exposure_fraction),
        "max_protected_amount": max(0.0, max_bet_by_exposure),
        "estimated_player_edge": edge,
        "estimated_risk_of_ruin": min(1.0, max(0.0, estimated_risk)),
        "risk_of_ruin_limit": risk_limit,
        "risk_model": RISK_MODEL,
        "variance_per_unit": variance,
        "max_bet_by_risk": max(0.0, max_bet_by_risk),
        "max_single_round_exposure": round_cap,
        "max_bet_by_exposure": max(0.0, max_bet_by_exposure),
        "selected_bet_fraction": max(0.0, exposure_fraction),
        "kelly_fraction": kelly_fraction,
        "risk_limited_fraction": max(0.0, risk_limited_fraction),
        "risk_if_minimum_bet": _optional_probability(risk_if_minimum_bet),
        "minimum_bankroll_required_for_minimum_bet": (
            _optional_non_negative_finite(
                minimum_bankroll_required_for_minimum_bet
            )
        ),
        "minimum_bet_exceeds_risk_cap": bool(minimum_bet_exceeds_risk_cap),
        "recommendation_status": status,
        "recommendation_text": _STATUS_TEXT[status],
        "warnings": list(warnings),
        "constants": {
            "variance_per_unit": variance,
            "risk_of_ruin_limit": risk_limit,
            "max_single_round_exposure": round_cap,
            "max_bankroll_exposure": round_cap,
            "risk_model": RISK_MODEL,
        },
    }
    if system_id is not None:
        result["system_id"] = system_id
    return result


def _enforce_risk_limit_after_rounding(
    *,
    bankroll: float,
    minimum_bet: float,
    edge: float,
    variance: float,
    risk_limit: float,
    suggested_units: int,
) -> tuple[int, float, float]:
    units = max(0, suggested_units)
    while units > 0:
        amount = float(Fraction(units) * Fraction.from_float(minimum_bet))
        risk = estimate_risk_of_ruin(
            bankroll=bankroll,
            bet_amount=amount,
            estimated_player_edge=edge,
            variance_per_unit=variance,
        )
        if risk <= risk_limit:
            return units, amount, risk
        units -= 1
    return 0, 0.0, 0.0


def _optional_finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    converted = float(value)
    return converted if math.isfinite(converted) else None


def _require_finite_number(value: object, name: str) -> float:
    converted = _optional_finite_number(value)
    if converted is None:
        raise ValueError(f"{name} must be a finite number")
    return converted


def _require_positive_finite_number(value: object, name: str) -> float:
    converted = _require_finite_number(value, name)
    if converted <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return converted


def _validate_risk_limit(value: object) -> float:
    converted = _require_finite_number(value, "risk_of_ruin_limit")
    if converted <= 0 or converted >= 1:
        raise ValueError("risk_of_ruin_limit must be greater than 0 and less than 1")
    return converted


def _validate_exposure_fraction(value: object) -> float:
    converted = _require_finite_number(
        value,
        "max_single_round_exposure",
    )
    if converted <= 0 or converted > 1:
        raise ValueError(
            "max_single_round_exposure must be greater than 0 and at most 1"
        )
    return converted


def _validate_cards_remaining(cards_remaining: int | None) -> None:
    if cards_remaining is None:
        return
    if (
        isinstance(cards_remaining, bool)
        or not isinstance(cards_remaining, int)
        or cards_remaining < 0
    ):
        raise ValueError("cards_remaining must be a non-negative integer")


def _calculate_discrete_exposure(
    available_amount: float,
    minimum_bet: float,
) -> tuple[int, float]:
    amount_fraction = Fraction.from_float(available_amount)
    minimum_fraction = Fraction.from_float(minimum_bet)
    suggested_units = max(0, amount_fraction // minimum_fraction)
    suggested_amount = float(suggested_units * minimum_fraction)

    if suggested_amount > available_amount and suggested_units > 0:
        suggested_units -= 1
        suggested_amount = float(suggested_units * minimum_fraction)

    return suggested_units, suggested_amount


def _optional_probability(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return min(1.0, max(0.0, value))


def _optional_non_negative_finite(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return max(0.0, value)
