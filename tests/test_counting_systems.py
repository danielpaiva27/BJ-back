import math

import pytest

from blackjack_risk_engine.engine_core.counting import (
    calculate_count_snapshot,
    calculate_running_count,
    calculate_scaled_running_count,
    calculate_true_count,
    get_count_system,
    list_count_systems,
    validate_seen_cards_against_shoe,
)


def test_hi_lo_basic_running_count() -> None:
    seen_cards = ["2", "3", "10", "A"]

    assert calculate_running_count("hi_lo", seen_cards) == 0


def test_hi_opt_ii_basic_running_count() -> None:
    seen_cards = ["4", "5", "10", "A"]

    assert calculate_running_count("hi_opt_ii", seen_cards) == 2


def test_wong_halves_uses_scaled_integer_running_count() -> None:
    seen_cards = ["2", "5", "9", "10", "A"]

    assert calculate_scaled_running_count("wong_halves", seen_cards) == -1
    assert calculate_running_count("wong_halves", seen_cards) == -0.5


def test_true_count_uses_decks_remaining() -> None:
    snapshot = calculate_count_snapshot("hi_lo", ["2"], number_of_decks=6)

    expected_true_count = 1 / (311 / 52)

    assert snapshot["decks_remaining"] == 311 / 52
    assert snapshot["true_count"] == pytest.approx(expected_true_count)


def test_true_count_never_returns_nan_or_infinity_at_end_of_shoe() -> None:
    assert calculate_true_count(4, 0) == 0.0
    assert calculate_true_count(4, -0.1) == 0.0
    assert math.isfinite(calculate_true_count(4, 1 / 52))


def test_invalid_card_raises_clear_error() -> None:
    with pytest.raises(ValueError, match=r"invalid blackjack card 'X'"):
        calculate_running_count("hi_lo", ["X"])


def test_invalid_system_raises_clear_error() -> None:
    with pytest.raises(ValueError, match=r"unknown count system 'banana_count'"):
        get_count_system("banana_count")


def test_too_many_aces_for_shoe_raises_clear_error() -> None:
    with pytest.raises(ValueError, match=r"5 copies of A"):
        validate_seen_cards_against_shoe(["A"] * 5, number_of_decks=1)


def test_too_many_ten_value_cards_for_shoe_raises_clear_error() -> None:
    with pytest.raises(ValueError, match=r"17 copies of 10"):
        validate_seen_cards_against_shoe(["10"] * 17, number_of_decks=1)


def test_list_count_systems_returns_all_supported_systems() -> None:
    systems = list_count_systems()

    assert [system.system_id for system in systems] == [
        "hi_lo",
        "hi_opt_ii",
        "wong_halves",
    ]


@pytest.mark.parametrize(
    ("system_id", "scale", "scaled_weights"),
    [
        ("hi_lo", 1, (-1, 1, 1, 1, 1, 1, 0, 0, 0, -1)),
        ("hi_opt_ii", 1, (0, 1, 1, 2, 2, 1, 1, 0, 0, -2)),
        ("wong_halves", 2, (-2, 1, 2, 2, 3, 2, 1, 0, -1, -2)),
    ],
)
def test_count_system_defines_expected_weights(
    system_id: str,
    scale: int,
    scaled_weights: tuple[int, ...],
) -> None:
    system = get_count_system(system_id)

    assert system.scale == scale
    assert system.scaled_weights == scaled_weights


@pytest.mark.parametrize(
    ("system_id", "expected"),
    [
        (
            "hi_lo",
            {
                "label": "Hi-Lo",
                "level": 1,
                "balanced": True,
                "ace_reckoned": True,
                "fractional": False,
                "requires_ace_side_count": False,
            },
        ),
        (
            "hi_opt_ii",
            {
                "label": "Hi-Opt II",
                "level": 2,
                "balanced": True,
                "ace_reckoned": False,
                "fractional": False,
                "requires_ace_side_count": True,
            },
        ),
        (
            "wong_halves",
            {
                "label": "Wong Halves",
                "level": 3,
                "balanced": True,
                "ace_reckoned": True,
                "fractional": True,
                "requires_ace_side_count": False,
            },
        ),
    ],
)
def test_snapshot_contains_count_and_system_metadata(
    system_id: str,
    expected: dict[str, str | bool | int],
) -> None:
    snapshot = calculate_count_snapshot(system_id, [], number_of_decks=6)

    assert snapshot["system_id"] == system_id
    for key, value in expected.items():
        assert snapshot[key] == value
    assert snapshot["running_count"] == 0
    assert snapshot["true_count"] == 0
    assert snapshot["cards_seen"] == 0
    assert snapshot["cards_remaining"] == 312
    assert snapshot["decks_remaining"] == 6


def test_wong_halves_snapshot_exposes_scale_and_scaled_count() -> None:
    snapshot = calculate_count_snapshot(
        "wong_halves",
        ["2", "5", "9", "10", "A"],
        number_of_decks=6,
    )

    assert snapshot["scale"] == 2
    assert snapshot["scaled_running_count"] == -1
    assert snapshot["running_count"] == -0.5


@pytest.mark.parametrize("number_of_decks", [0, -1, 1.5, True])
def test_number_of_decks_must_be_a_positive_integer(
    number_of_decks: object,
) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        calculate_count_snapshot(
            "hi_lo",
            [],
            number_of_decks=number_of_decks,  # type: ignore[arg-type]
        )


def test_full_valid_shoe_has_safe_zero_true_count() -> None:
    full_shoe = (
        ["A"] * 4
        + ["2"] * 4
        + ["3"] * 4
        + ["4"] * 4
        + ["5"] * 4
        + ["6"] * 4
        + ["7"] * 4
        + ["8"] * 4
        + ["9"] * 4
        + ["10"] * 16
    )

    snapshot = calculate_count_snapshot("wong_halves", full_shoe, 1)

    assert snapshot["cards_remaining"] == 0
    assert snapshot["decks_remaining"] == 0
    assert snapshot["true_count"] == 0.0
    assert math.isfinite(snapshot["true_count"])
