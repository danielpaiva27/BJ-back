from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from numbers import Real
from typing import TypeAlias

from blackjack_risk_engine.engine_core.counting import (
    calculate_count_snapshot,
    calculate_true_count,
    get_count_system,
    list_count_systems,
    validate_seen_cards_against_shoe,
)
from blackjack_risk_engine.engine_core.pre_round.bankroll_policy import (
    get_bankroll_policy_info,
    suggest_bankroll_exposure,
)
from blackjack_risk_engine.engine_core.pre_round.edge_estimation import (
    estimate_player_edge,
)


ACE_ADJUSTMENT_FACTOR = 2

PreRoundSystemAnalysis: TypeAlias = dict[str, object]
PreRoundAnalysis: TypeAlias = dict[str, object]

_BANKROLL_RESULT_FIELDS = (
    "should_enter",
    "suggested_units",
    "suggested_amount",
    "bankroll_exposure_percent",
    "max_protected_amount",
    "estimated_risk_of_ruin",
    "risk_of_ruin_limit",
    "risk_model",
    "variance_per_unit",
    "max_bet_by_risk",
    "max_single_round_exposure",
    "max_bet_by_exposure",
    "selected_bet_fraction",
    "kelly_fraction",
    "risk_limited_fraction",
    "risk_if_minimum_bet",
    "minimum_bankroll_required_for_minimum_bet",
    "minimum_bet_exceeds_risk_cap",
    "recommendation_status",
    "recommendation_text",
    "warnings",
)


def analyze_pre_round(
    number_of_decks: int,
    seen_cards: Iterable[str],
    bankroll: float,
    minimum_bet: float,
    rules: object | Mapping[str, object] | None = None,
    systems: Iterable[str] | None = None,
) -> PreRoundAnalysis:
    """Combine count, estimated edge, and protected bankroll exposure.

    The result is a deterministic pre-round heuristic. It does not represent
    the exact expected value of the next hand and does not alter hand-play
    strategy.
    """

    normalized_cards = validate_seen_cards_against_shoe(
        seen_cards,
        number_of_decks,
    )
    selected_system_ids = _normalize_system_ids(systems)
    bankroll_value = _finite_float(bankroll, "bankroll")
    minimum_bet_value = _finite_float(minimum_bet, "minimum_bet")

    cards_seen = len(normalized_cards)
    cards_remaining = (number_of_decks * 52) - cards_seen
    decks_remaining = _safe_decks_remaining(cards_remaining)

    system_results = [
        _analyze_system(
            system_id=system_id,
            seen_cards=normalized_cards,
            number_of_decks=number_of_decks,
            bankroll=bankroll_value,
            minimum_bet=minimum_bet_value,
            rules=rules,
        )
        for system_id in selected_system_ids
    ]
    most_favorable = max(
        system_results,
        key=lambda result: float(result["estimated_player_edge"]),
    )

    return {
        "cards_seen": cards_seen,
        "cards_remaining": cards_remaining,
        "decks_remaining": decks_remaining,
        "bankroll": bankroll_value,
        "minimum_bet": minimum_bet_value,
        "policy": get_bankroll_policy_info(),
        "systems": system_results,
        "most_favorable_estimate_system_id": most_favorable["system_id"],
    }


def _analyze_system(
    *,
    system_id: str,
    seen_cards: tuple[str, ...],
    number_of_decks: int,
    bankroll: float,
    minimum_bet: float,
    rules: object | Mapping[str, object] | None,
) -> PreRoundSystemAnalysis:
    snapshot = calculate_count_snapshot(
        system_id,
        seen_cards,
        number_of_decks,
    )

    if system_id == "hi_opt_ii":
        result = _build_hi_opt_ii_count_result(
            snapshot,
            seen_cards,
            number_of_decks,
        )
    else:
        result = dict(snapshot)
        result["betting_true_count"] = snapshot["true_count"]

    betting_true_count = float(result["betting_true_count"])
    estimated_edge = estimate_player_edge(
        betting_true_count=betting_true_count,
        rules=rules,
        system_id=system_id,
    )
    bankroll_suggestion = suggest_bankroll_exposure(
        bankroll=bankroll,
        minimum_bet=minimum_bet,
        estimated_player_edge=estimated_edge,
        cards_remaining=int(snapshot["cards_remaining"]),
        system_id=system_id,
    )

    result["estimated_player_edge"] = estimated_edge
    for field in _BANKROLL_RESULT_FIELDS:
        result[field] = bankroll_suggestion[field]
    return result


def _build_hi_opt_ii_count_result(
    snapshot: Mapping[str, str | bool | int | float],
    seen_cards: tuple[str, ...],
    number_of_decks: int,
) -> PreRoundSystemAnalysis:
    playing_running_count = float(snapshot["running_count"])
    playing_true_count = float(snapshot["true_count"])
    cards_remaining = int(snapshot["cards_remaining"])
    decks_remaining = float(snapshot["decks_remaining"])

    total_aces = number_of_decks * 4
    seen_aces = sum(card == "A" for card in seen_cards)
    aces_remaining = total_aces - seen_aces
    expected_aces_remaining = decks_remaining * 4
    excess_aces = aces_remaining - expected_aces_remaining
    betting_running_count = (
        playing_running_count
        + (excess_aces * ACE_ADJUSTMENT_FACTOR)
    )
    betting_true_count = calculate_true_count(
        betting_running_count,
        decks_remaining,
    )

    result: PreRoundSystemAnalysis = dict(snapshot)
    result.update(
        {
            "playing_running_count": snapshot["running_count"],
            "playing_true_count": playing_true_count,
            "ace_side_count": {
                "total_aces": total_aces,
                "seen_aces": seen_aces,
                "aces_remaining": aces_remaining,
                "expected_aces_remaining": expected_aces_remaining,
                "excess_aces": excess_aces,
            },
            "ace_adjustment_factor": ACE_ADJUSTMENT_FACTOR,
            "betting_running_count": betting_running_count,
            "betting_true_count": betting_true_count,
        }
    )

    if cards_remaining <= 0:
        result["betting_true_count"] = 0.0
    return result


def _normalize_system_ids(systems: Iterable[str] | None) -> tuple[str, ...]:
    if systems is None:
        return tuple(system.system_id for system in list_count_systems())
    if isinstance(systems, (str, bytes)):
        raise ValueError("systems must be an iterable of counting system ids")

    try:
        requested_systems = tuple(systems)
    except TypeError as error:
        raise ValueError(
            "systems must be an iterable of counting system ids"
        ) from error

    if not requested_systems:
        raise ValueError("At least one counting system must be provided.")

    normalized_ids: list[str] = []
    for system_id in requested_systems:
        system = get_count_system(system_id)
        if system.system_id in normalized_ids:
            raise ValueError(
                f"counting system {system.system_id!r} was provided more than once"
            )
        normalized_ids.append(system.system_id)
    return tuple(normalized_ids)


def _finite_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    try:
        converted = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be a finite number")
    return converted


def _safe_decks_remaining(cards_remaining: int) -> float:
    try:
        decks_remaining = cards_remaining / 52
    except OverflowError as error:
        raise ValueError("number_of_decks is too large") from error
    if not math.isfinite(decks_remaining):
        raise ValueError("number_of_decks is too large")
    return decks_remaining
