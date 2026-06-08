from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Real
from typing import Any


BASE_HOUSE_EDGE = 0.005
EDGE_PER_TRUE_COUNT = 0.005
BLACKJACK_SIX_TO_FIVE_PENALTY = 0.014
DEALER_HITS_SOFT_17_PENALTY = 0.002
SURRENDER_ALLOWED_BENEFIT = 0.0005
DOUBLE_AFTER_SPLIT_BENEFIT = 0.001


def estimate_player_edge(
    betting_true_count: float,
    rules: object | Mapping[str, object] | None = None,
    system_id: str | None = None,
) -> float:
    """Estimate pre-round player edge using a documented count heuristic.

    This is not the exact expected value of the next hand. It applies a
    0.5-percentage-point improvement per true-count point to a neutral
    0.5% house-edge baseline, then makes small heuristic rule adjustments.
    ``system_id`` is accepted for the future multi-system endpoint but does
    not change the estimate in this stage.
    """

    del system_id
    true_count = _finite_float(betting_true_count, "betting_true_count")
    adjusted_base_house_edge = BASE_HOUSE_EDGE

    payout = _get_rule_value(rules, "blackjack_payout", default=None)
    if payout is None:
        payout = _get_rule_value(
            rules,
            "blackjack_payout_multiplier",
            default=None,
        )
    if _is_six_to_five_payout(payout):
        adjusted_base_house_edge += BLACKJACK_SIX_TO_FIVE_PENALTY

    if _get_rule_value(rules, "dealer_hits_soft_17", default=False) is True:
        adjusted_base_house_edge += DEALER_HITS_SOFT_17_PENALTY

    if _get_rule_value(rules, "surrender_allowed", default=False) is True:
        adjusted_base_house_edge -= SURRENDER_ALLOWED_BENEFIT

    if _get_rule_value(rules, "double_after_split", default=False) is True:
        adjusted_base_house_edge -= DOUBLE_AFTER_SPLIT_BENEFIT

    estimated_edge = (true_count * EDGE_PER_TRUE_COUNT) - adjusted_base_house_edge
    if not math.isfinite(estimated_edge):
        raise ValueError("estimated player edge must be finite")
    return estimated_edge


def _get_rule_value(
    rules: object | Mapping[str, object] | None,
    name: str,
    default: Any,
) -> Any:
    if rules is None:
        return default
    if isinstance(rules, Mapping):
        return rules.get(name, default)
    try:
        return getattr(rules, name, default)
    except (AttributeError, TypeError, ValueError):
        return default


def _is_six_to_five_payout(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, Real):
        numeric_value = float(value)
        return math.isfinite(numeric_value) and math.isclose(
            numeric_value,
            1.2,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
    if not isinstance(value, str):
        return False

    normalized = value.strip().lower().replace(" ", "")
    if normalized in {"6:5", "6/5"}:
        return True
    try:
        numeric_value = float(normalized)
    except ValueError:
        return False
    return math.isfinite(numeric_value) and math.isclose(
        numeric_value,
        1.2,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def _finite_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be a finite number")
    return converted
