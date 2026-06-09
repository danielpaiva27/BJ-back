from __future__ import annotations

from collections.abc import Iterable, Mapping

from blackjack_risk_engine.engine_core.cards import (
    RANK_STRINGS,
    RANK_TO_INDEX,
    rank_to_string,
    string_to_rank,
)
from blackjack_risk_engine.engine_core.pre_round.machine_ev.config import (
    MachineEvConfig,
)
from blackjack_risk_engine.engine_core.pre_round.machine_ev.models import (
    MachineEvInitialState,
    MachineEvInitialStateKey,
)


def canonicalize_player_cards(cards: Iterable[str]) -> tuple[str, str]:
    card_tuple = tuple(cards)
    if len(card_tuple) != 2:
        raise ValueError("player_cards must contain exactly two cards")

    rank_indexes = sorted(string_to_rank(card) for card in card_tuple)
    return rank_to_string(rank_indexes[0]), rank_to_string(rank_indexes[1])


def make_shoe_signature(shoe_counts: Mapping[str, int]) -> tuple[int, ...]:
    return _validate_shoe_counts(shoe_counts)


def make_initial_state_key(
    player_cards: Iterable[str],
    dealer_upcard: str,
    shoe_after: Mapping[str, int],
) -> MachineEvInitialStateKey:
    canonical_cards = canonicalize_player_cards(player_cards)
    normalized_dealer_upcard = rank_to_string(string_to_rank(dealer_upcard))
    shoe_signature = make_shoe_signature(shoe_after)
    return canonical_cards, normalized_dealer_upcard, shoe_signature


def enumerate_observable_initial_states(
    shoe_counts: Mapping[str, int],
    config: MachineEvConfig | None = None,
) -> tuple[MachineEvInitialState, ...]:
    if config is not None and not isinstance(config, MachineEvConfig):
        raise ValueError("config must be a MachineEvConfig or None")

    initial_signature = _validate_shoe_counts(shoe_counts, minimum_cards=3)
    counts = list(initial_signature)
    total_cards = sum(counts)
    aggregated: dict[MachineEvInitialStateKey, tuple[float, int]] = {}

    for player_card_1, player_card_1_count in enumerate(counts):
        if player_card_1_count == 0:
            continue

        player_card_1_probability = player_card_1_count / total_cards
        counts[player_card_1] -= 1

        for dealer_upcard, dealer_upcard_count in enumerate(counts):
            if dealer_upcard_count == 0:
                continue

            dealer_upcard_probability = dealer_upcard_count / (total_cards - 1)
            counts[dealer_upcard] -= 1

            for player_card_2, player_card_2_count in enumerate(counts):
                if player_card_2_count == 0:
                    continue

                path_probability = (
                    player_card_1_probability
                    * dealer_upcard_probability
                    * player_card_2_count
                    / (total_cards - 2)
                )
                counts[player_card_2] -= 1

                canonical_cards = _canonical_cards_from_rank_indexes(
                    player_card_1,
                    player_card_2,
                )
                dealer_upcard_rank = rank_to_string(dealer_upcard)
                shoe_signature = tuple(counts)
                key = _make_initial_state_key_from_signature(
                    canonical_cards,
                    dealer_upcard_rank,
                    shoe_signature,
                )
                current_probability, current_path_count = aggregated.get(
                    key,
                    (0.0, 0),
                )
                aggregated[key] = (
                    current_probability + path_probability,
                    current_path_count + 1,
                )

                counts[player_card_2] += 1

            counts[dealer_upcard] += 1

        counts[player_card_1] += 1

    return tuple(
        MachineEvInitialState(
            player_cards=key[0],
            dealer_upcard=key[1],
            shoe_after=_shoe_items(key[2]),
            probability=probability,
            canonical_key=key,
            path_count=path_count,
        )
        for key, (probability, path_count) in sorted(aggregated.items())
    )


def _validate_shoe_counts(
    shoe_counts: Mapping[str, int],
    minimum_cards: int | None = None,
) -> tuple[int, ...]:
    if not isinstance(shoe_counts, Mapping):
        raise ValueError("shoe_counts must be a mapping of ranks to counts")

    for rank, count in shoe_counts.items():
        if rank not in RANK_TO_INDEX:
            raise ValueError(f"Invalid rank in shoe counts: {rank}")
        if isinstance(count, bool) or not isinstance(count, int):
            raise ValueError("Shoe counts must contain integer values.")
        if count < 0:
            raise ValueError("Shoe counts cannot contain negative values.")

    signature = tuple(shoe_counts.get(rank, 0) for rank in RANK_STRINGS)
    if minimum_cards is not None and sum(signature) < minimum_cards:
        raise ValueError(
            f"At least {minimum_cards} cards are required to enumerate an initial state."
        )
    return signature


def _canonical_cards_from_rank_indexes(
    first_card: int,
    second_card: int,
) -> tuple[str, str]:
    low_rank, high_rank = sorted((first_card, second_card))
    return rank_to_string(low_rank), rank_to_string(high_rank)


def _make_initial_state_key_from_signature(
    player_cards: tuple[str, str],
    dealer_upcard: str,
    shoe_signature: tuple[int, ...],
) -> MachineEvInitialStateKey:
    return player_cards, dealer_upcard, shoe_signature


def _shoe_items(
    shoe_signature: tuple[int, ...],
) -> tuple[tuple[str, int], ...]:
    return tuple(zip(RANK_STRINGS, shoe_signature, strict=True))
