from dataclasses import fields
import inspect
import math

import pytest

from blackjack_risk_engine.engine_core.cards import ONE_DECK_COUNTS, RANK_STRINGS
from blackjack_risk_engine.engine_core.pre_round.machine_ev import (
    MachineEvInitialState,
    canonicalize_player_cards,
    enumerate_observable_initial_states,
    make_initial_state_key,
    make_shoe_signature,
)
import blackjack_risk_engine.engine_core.pre_round.machine_ev.predeal_enumerator as enumerator_module


def _shoe_for_decks(number_of_decks: int) -> dict[str, int]:
    return {
        rank: count * number_of_decks
        for rank, count in zip(RANK_STRINGS, ONE_DECK_COUNTS, strict=True)
    }


def _assert_valid_states(states: tuple[MachineEvInitialState, ...]) -> None:
    assert states
    assert sum(state.probability for state in states) == pytest.approx(1.0)

    for state in states:
        assert math.isfinite(state.probability)
        assert 0 <= state.probability <= 1
        assert all(count >= 0 for _, count in state.shoe_after)


def test_enumerates_complete_one_deck_shoe() -> None:
    states = enumerate_observable_initial_states(_shoe_for_decks(1))

    _assert_valid_states(states)
    assert all(sum(count for _, count in state.shoe_after) == 49 for state in states)


def test_enumerates_complete_six_deck_shoe() -> None:
    states = enumerate_observable_initial_states(_shoe_for_decks(6))

    _assert_valid_states(states)
    assert all(sum(count for _, count in state.shoe_after) == 309 for state in states)


def test_canonicalizes_player_cards_and_builds_stable_key() -> None:
    shoe_after = {"A": 1, "2": 2, "10": 3}

    assert canonicalize_player_cards(("8", "10")) == ("8", "10")
    assert canonicalize_player_cards(("10", "8")) == ("8", "10")
    assert make_initial_state_key(
        ("8", "10"),
        "6",
        shoe_after,
    ) == make_initial_state_key(
        ("10", "8"),
        "6",
        {"10": 3, "2": 2, "A": 1},
    )


def test_equivalent_player_card_paths_are_aggregated() -> None:
    states = enumerate_observable_initial_states({"8": 1, "10": 1, "6": 1})

    state = next(
        item
        for item in states
        if item.player_cards == ("8", "10") and item.dealer_upcard == "6"
    )

    assert state.probability == pytest.approx(1 / 3)
    assert state.path_count == 2
    assert sum(count for _, count in state.shoe_after) == 0


def test_three_card_shoe_enumerates_all_observable_states() -> None:
    states = enumerate_observable_initial_states({"A": 1, "2": 1, "10": 1})

    _assert_valid_states(states)
    assert len(states) == 3
    assert all(sum(count for _, count in state.shoe_after) == 0 for state in states)


def test_rejects_shoe_with_fewer_than_three_cards() -> None:
    with pytest.raises(ValueError, match="At least 3 cards"):
        enumerate_observable_initial_states({"A": 1, "10": 1})


def test_rejects_invalid_rank() -> None:
    with pytest.raises(ValueError, match="Invalid rank in shoe counts: X"):
        enumerate_observable_initial_states({"X": 1, "A": 4})


def test_rejects_negative_count() -> None:
    with pytest.raises(ValueError, match="cannot contain negative"):
        enumerate_observable_initial_states({"A": -1})


def test_rejects_non_integer_count() -> None:
    with pytest.raises(ValueError, match="integer values"):
        enumerate_observable_initial_states({"A": 1.5})  # type: ignore[dict-item]


def test_missing_ranks_are_treated_as_zero() -> None:
    states = enumerate_observable_initial_states({"A": 1, "2": 1, "10": 1})

    assert states
    assert all(dict(state.shoe_after)["3"] == 0 for state in states)


def test_shoe_signature_uses_fixed_rank_order() -> None:
    first = make_shoe_signature({"10": 10, "A": 1, "5": 5})
    second = make_shoe_signature({"5": 5, "A": 1, "10": 10})

    assert first == second
    assert first == (1, 0, 0, 0, 5, 0, 0, 0, 0, 10)


def test_initial_state_does_not_expose_dealer_hole_card() -> None:
    field_names = {field.name for field in fields(MachineEvInitialState)}
    state = enumerate_observable_initial_states({"A": 1, "2": 1, "10": 1})[0]

    assert "dealer_hole_card" not in field_names
    assert not hasattr(state, "dealer_hole_card")
    assert sum(count for _, count in state.shoe_after) == 0


def test_enumerator_does_not_depend_on_decision_engine() -> None:
    source = inspect.getsource(enumerator_module)

    assert "action_ev" not in source
    assert "deterministic_analysis" not in source
    assert "hybrid_analysis" not in source
    assert "monte_carlo_analysis" not in source


def test_enumerator_does_not_mutate_input_shoe() -> None:
    shoe_counts = {"A": 1, "2": 1, "10": 2}
    original = shoe_counts.copy()

    enumerate_observable_initial_states(shoe_counts)

    assert shoe_counts == original
