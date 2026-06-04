from __future__ import annotations

from collections.abc import Iterable
from typing import TypeAlias


RankIndex: TypeAlias = int

RANK_STRINGS: tuple[str, ...] = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10")
RANK_TO_INDEX: dict[str, RankIndex] = {rank: index for index, rank in enumerate(RANK_STRINGS)}
CARD_VALUES: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
HI_LO_WEIGHTS: tuple[int, ...] = (-1, 1, 1, 1, 1, 1, 0, 0, 0, -1)
ONE_DECK_COUNTS: tuple[int, ...] = (4, 4, 4, 4, 4, 4, 4, 4, 4, 16)


def string_to_rank(card: str) -> RankIndex:
    normalized = card.strip().upper()
    try:
        return RANK_TO_INDEX[normalized]
    except KeyError as error:
        allowed = ", ".join(RANK_STRINGS)
        raise ValueError(f"invalid blackjack card {card!r}; expected one of: {allowed}") from error


def rank_to_string(rank: RankIndex) -> str:
    _validate_rank(rank)
    return RANK_STRINGS[rank]


def card_value(rank: RankIndex) -> int:
    _validate_rank(rank)
    return CARD_VALUES[rank]


def hi_lo_weight(rank: RankIndex) -> int:
    _validate_rank(rank)
    return HI_LO_WEIGHTS[rank]


def deck_counts_for_decks(number_of_decks: int) -> tuple[int, ...]:
    if not isinstance(number_of_decks, int) or number_of_decks <= 0:
        raise ValueError("number_of_decks must be a positive integer")
    return tuple(count * number_of_decks for count in ONE_DECK_COUNTS)


def ordered_deck_ranks_for_decks(number_of_decks: int) -> tuple[RankIndex, ...]:
    if not isinstance(number_of_decks, int) or number_of_decks <= 0:
        raise ValueError("number_of_decks must be a positive integer")

    one_deck: list[RankIndex] = []
    for rank, count in enumerate(ONE_DECK_COUNTS):
        one_deck.extend([rank] * count)
    return tuple(one_deck * number_of_decks)


def remove_ranks_from_counts(
    deck_counts: Iterable[int],
    removed_ranks: Iterable[RankIndex],
) -> tuple[int, ...]:
    counts = list(deck_counts)
    if len(counts) != len(RANK_STRINGS):
        raise ValueError("deck_counts must contain exactly 10 ranks")

    for rank in removed_ranks:
        _validate_rank(rank)
        counts[rank] -= 1
        if counts[rank] < 0:
            raise ValueError(f"cannot remove card {rank_to_string(rank)}: not present in shoe")

    return tuple(counts)


def deck_counts_after_removal(
    number_of_decks: int,
    removed_ranks: Iterable[RankIndex],
) -> tuple[int, ...]:
    return remove_ranks_from_counts(deck_counts_for_decks(number_of_decks), removed_ranks)


def remove_ranks_preserving_order(
    deck_ranks: Iterable[RankIndex],
    removed_ranks: Iterable[RankIndex],
) -> tuple[RankIndex, ...]:
    remaining = list(deck_ranks)
    for rank in removed_ranks:
        _validate_rank(rank)
        try:
            remaining.remove(rank)
        except ValueError as error:
            raise ValueError(f"cannot remove card {rank_to_string(rank)}: not present in shoe") from error
    return tuple(remaining)


def remaining_ordered_deck_ranks(
    number_of_decks: int,
    removed_ranks: Iterable[RankIndex],
) -> tuple[RankIndex, ...]:
    return remove_ranks_preserving_order(
        ordered_deck_ranks_for_decks(number_of_decks),
        removed_ranks,
    )


def expand_deck_counts(deck_counts: Iterable[int]) -> tuple[RankIndex, ...]:
    counts = tuple(deck_counts)
    if len(counts) != len(RANK_STRINGS):
        raise ValueError("deck_counts must contain exactly 10 ranks")

    ranks: list[RankIndex] = []
    for rank, count in enumerate(counts):
        if count < 0:
            raise ValueError("deck_counts cannot contain negative values")
        ranks.extend([rank] * count)
    return tuple(ranks)


def _validate_rank(rank: RankIndex) -> None:
    if not isinstance(rank, int) or rank < 0 or rank >= len(RANK_STRINGS):
        raise ValueError(f"invalid internal rank {rank!r}; expected 0 through 9")
