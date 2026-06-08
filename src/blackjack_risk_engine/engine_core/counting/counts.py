from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from numbers import Real
from typing import TypeAlias

from blackjack_risk_engine.engine_core.cards import (
    RANK_STRINGS,
    RankIndex,
    deck_counts_for_decks,
    rank_to_string,
    string_to_rank,
)
from blackjack_risk_engine.engine_core.counting.systems import (
    CountSystem,
    get_count_system,
)


RunningCount: TypeAlias = int | float
CountSnapshot: TypeAlias = dict[str, str | bool | int | float]


def validate_seen_cards_against_shoe(
    seen_cards: Iterable[str],
    number_of_decks: int,
) -> tuple[str, ...]:
    _validate_number_of_decks(number_of_decks)
    ranks = _normalize_seen_cards(seen_cards)
    seen_counts = Counter(ranks)
    shoe_counts = deck_counts_for_decks(number_of_decks)

    for rank, seen_count in seen_counts.items():
        available_count = shoe_counts[rank]
        if seen_count > available_count:
            card = rank_to_string(rank)
            raise ValueError(
                f"seen_cards contains {seen_count} copies of {card}, "
                f"but a {number_of_decks}-deck shoe contains at most {available_count}"
            )

    return tuple(rank_to_string(rank) for rank in ranks)


def calculate_scaled_running_count(
    system_id: str,
    seen_cards: Iterable[str],
) -> int:
    system = get_count_system(system_id)
    ranks = _normalize_seen_cards(seen_cards)
    return _calculate_scaled_running_count(system, ranks)


def calculate_running_count(
    system_id: str,
    seen_cards: Iterable[str],
) -> RunningCount:
    system = get_count_system(system_id)
    ranks = _normalize_seen_cards(seen_cards)
    scaled_running_count = _calculate_scaled_running_count(system, ranks)
    return _unscale_count(scaled_running_count, system.scale)


def calculate_true_count(
    running_count: RunningCount,
    decks_remaining: float,
) -> float:
    _validate_finite_number(running_count, "running_count")
    _validate_finite_number(decks_remaining, "decks_remaining")

    if decks_remaining <= 0:
        return 0.0

    true_count = float(running_count) / float(decks_remaining)
    return true_count if math.isfinite(true_count) else 0.0


def calculate_count_snapshot(
    system_id: str,
    seen_cards: Iterable[str],
    number_of_decks: int,
) -> CountSnapshot:
    system = get_count_system(system_id)
    normalized_cards = validate_seen_cards_against_shoe(
        seen_cards,
        number_of_decks,
    )
    ranks = tuple(string_to_rank(card) for card in normalized_cards)
    scaled_running_count = _calculate_scaled_running_count(system, ranks)
    running_count = _unscale_count(scaled_running_count, system.scale)

    cards_seen = len(ranks)
    cards_remaining = (number_of_decks * 52) - cards_seen
    decks_remaining = cards_remaining / 52
    true_count = calculate_true_count(running_count, decks_remaining)

    snapshot: CountSnapshot = {
        "system_id": system.system_id,
        "label": system.label,
        "level": system.level,
        "balanced": system.balanced,
        "ace_reckoned": system.ace_reckoned,
        "fractional": system.fractional,
        "requires_ace_side_count": system.requires_ace_side_count,
        "running_count": running_count,
        "true_count": true_count,
        "cards_seen": cards_seen,
        "cards_remaining": cards_remaining,
        "decks_remaining": decks_remaining,
    }
    if system.fractional:
        snapshot["scale"] = system.scale
        snapshot["scaled_running_count"] = scaled_running_count

    return snapshot


def _normalize_seen_cards(seen_cards: Iterable[str]) -> tuple[RankIndex, ...]:
    if isinstance(seen_cards, (str, bytes)):
        raise ValueError("seen_cards must be an iterable of card strings")

    try:
        cards = tuple(seen_cards)
    except TypeError as error:
        raise ValueError("seen_cards must be an iterable of card strings") from error

    ranks: list[RankIndex] = []
    for card in cards:
        if not isinstance(card, str):
            allowed = ", ".join(RANK_STRINGS)
            raise ValueError(
                f"invalid blackjack card {card!r}; expected one of: {allowed}"
            )
        ranks.append(string_to_rank(card))
    return tuple(ranks)


def _calculate_scaled_running_count(
    system: CountSystem,
    ranks: Iterable[RankIndex],
) -> int:
    return sum(system.scaled_weight(rank) for rank in ranks)


def _unscale_count(scaled_count: int, scale: int) -> RunningCount:
    if scale == 1:
        return scaled_count
    return scaled_count / scale


def _validate_number_of_decks(number_of_decks: int) -> None:
    if (
        isinstance(number_of_decks, bool)
        or not isinstance(number_of_decks, int)
        or number_of_decks <= 0
    ):
        raise ValueError("number_of_decks must be a positive integer")


def _validate_finite_number(value: Real, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
