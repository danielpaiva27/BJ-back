from __future__ import annotations

from functools import lru_cache
from math import sqrt
from typing import NamedTuple

from blackjack_risk_engine.engine_core.cards import RANK_STRINGS, RankIndex, card_value
from blackjack_risk_engine.engine_core.hand import add_card_to_total


DEALER_TOTALS: tuple[int, ...] = (17, 18, 19, 20, 21)
DealerDistribution = tuple[float, float, float, float, float, float]


class StandEvResult(NamedTuple):
    expected_value: float
    win_rate: float
    lose_rate: float
    push_rate: float
    std_dev: float


def dealer_outcome_distribution(
    dealer_upcard_rank: RankIndex,
    deck_counts: tuple[int, ...],
    dealer_hits_soft_17: bool,
) -> DealerDistribution:
    """Return exact dealer outcome probabilities for the remaining shoe.

    `deck_counts` is the current remaining composition after removing known
    cards, including the dealer upcard. The dealer upcard is placed into the
    dealer hand before recursively drawing the hole card and any follow-up cards.
    """

    _validate_rank(dealer_upcard_rank)
    counts = _validate_deck_counts(deck_counts)
    if sum(counts) <= 0:
        raise ValueError("deck_counts must contain at least one card for the dealer hole card")

    total, soft_aces = add_card_to_total(0, 0, dealer_upcard_rank)
    return _cached_dealer_distribution(total, soft_aces, counts, bool(dealer_hits_soft_17))


def dealer_distribution_to_dict(distribution: DealerDistribution) -> dict[int | str, float]:
    return {
        17: distribution[0],
        18: distribution[1],
        19: distribution[2],
        20: distribution[3],
        21: distribution[4],
        "bust": distribution[5],
    }


def stand_ev_from_distribution(player_total: int, distribution: DealerDistribution) -> StandEvResult:
    if player_total > 21:
        return StandEvResult(-1.0, 0.0, 1.0, 0.0, 0.0)

    win_rate = distribution[5]
    lose_rate = 0.0
    push_rate = 0.0

    for index, dealer_total in enumerate(DEALER_TOTALS):
        probability = distribution[index]
        if player_total > dealer_total:
            win_rate += probability
        elif player_total < dealer_total:
            lose_rate += probability
        else:
            push_rate += probability

    expected_value = win_rate - lose_rate
    second_moment = win_rate + lose_rate
    variance = max(0.0, second_moment - expected_value * expected_value)
    return StandEvResult(
        expected_value=expected_value,
        win_rate=win_rate,
        lose_rate=lose_rate,
        push_rate=push_rate,
        std_dev=sqrt(variance),
    )


def natural_blackjack_stand_ev(
    dealer_upcard_rank: RankIndex,
    deck_counts: tuple[int, ...],
    blackjack_payout_multiplier: float,
) -> StandEvResult:
    counts = _validate_deck_counts(deck_counts)
    remaining = sum(counts)
    if remaining <= 0:
        raise ValueError("deck_counts must contain at least one card for the dealer hole card")

    dealer_blackjack_probability = 0.0
    if dealer_upcard_rank == 0:
        dealer_blackjack_probability = counts[9] / remaining
    elif dealer_upcard_rank == 9:
        dealer_blackjack_probability = counts[0] / remaining

    win_rate = 1.0 - dealer_blackjack_probability
    push_rate = dealer_blackjack_probability
    expected_value = win_rate * blackjack_payout_multiplier
    second_moment = win_rate * blackjack_payout_multiplier * blackjack_payout_multiplier
    variance = max(0.0, second_moment - expected_value * expected_value)
    return StandEvResult(
        expected_value=expected_value,
        win_rate=win_rate,
        lose_rate=0.0,
        push_rate=push_rate,
        std_dev=sqrt(variance),
    )


def dealer_distribution_cache_info() -> object:
    return _cached_dealer_distribution.cache_info()


def dealer_distribution_cache_clear() -> None:
    _cached_dealer_distribution.cache_clear()


@lru_cache(maxsize=200_000)
def _cached_dealer_distribution(
    total: int,
    soft_aces: int,
    deck_counts: tuple[int, ...],
    dealer_hits_soft_17: bool,
) -> DealerDistribution:
    if total > 21:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 1.0)

    if _dealer_stands(total, soft_aces, dealer_hits_soft_17):
        return _terminal_distribution(total)

    remaining_cards = sum(deck_counts)
    if remaining_cards <= 0:
        return _terminal_distribution(total)

    weighted = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    for rank, count in enumerate(deck_counts):
        if count <= 0:
            continue

        next_counts = list(deck_counts)
        next_counts[rank] -= 1
        next_total, next_soft_aces = add_card_to_total(total, soft_aces, rank)
        branch = _cached_dealer_distribution(
            next_total,
            next_soft_aces,
            tuple(next_counts),
            dealer_hits_soft_17,
        )
        probability = count / remaining_cards
        for index, value in enumerate(branch):
            weighted[index] += probability * value

    return tuple(weighted)  # type: ignore[return-value]


def _dealer_stands(total: int, soft_aces: int, dealer_hits_soft_17: bool) -> bool:
    if total < 17:
        return False
    if total == 17 and soft_aces > 0 and dealer_hits_soft_17:
        return False
    return True


def _terminal_distribution(total: int) -> DealerDistribution:
    if total > 21:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    if total in DEALER_TOTALS:
        values = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        values[total - 17] = 1.0
        return tuple(values)  # type: ignore[return-value]
    raise ValueError(f"dealer cannot stand on total {total}")


def _validate_deck_counts(deck_counts: tuple[int, ...]) -> tuple[int, ...]:
    counts = tuple(deck_counts)
    if len(counts) != len(RANK_STRINGS):
        raise ValueError("deck_counts must contain exactly 10 ranks")
    if any(not isinstance(count, int) for count in counts):
        raise ValueError("deck_counts must contain integer counts")
    if any(count < 0 for count in counts):
        raise ValueError("deck_counts cannot contain negative values")
    return counts


def _validate_rank(rank: RankIndex) -> None:
    if not isinstance(rank, int) or rank < 0 or rank >= len(RANK_STRINGS):
        raise ValueError(f"invalid internal rank {rank!r}; expected 0 through 9")
