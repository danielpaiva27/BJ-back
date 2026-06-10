from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from blackjack_risk_engine.engine_core.cards import ONE_DECK_COUNTS, RANK_STRINGS
from blackjack_risk_engine.engine_core.pre_round.machine_ev import (
    MachineEvInput,
    evaluate_machine_ev_pre_round,
)


@dataclass(frozen=True, slots=True)
class BenchmarkScenario:
    name: str
    number_of_decks: int
    seen_cards: tuple[str, ...]


def _full_shoe_cards(number_of_decks: int) -> list[str]:
    cards: list[str] = []
    for rank, count in zip(RANK_STRINGS, ONE_DECK_COUNTS, strict=True):
        cards.extend([rank] * count * number_of_decks)
    return cards


def _near_consumed_seen_cards() -> tuple[str, ...]:
    full_shoe = _full_shoe_cards(1)
    cards_left = (
        ["A"] * 2
        + ["2"] * 2
        + ["3"] * 2
        + ["4"] * 2
        + ["5"] * 2
        + ["6"] * 2
        + ["7"] * 2
        + ["8"] * 2
        + ["9"] * 2
        + ["10"] * 4
    )
    for card in cards_left:
        full_shoe.remove(card)
    return tuple(full_shoe)


SCENARIOS = (
    BenchmarkScenario("neutral_6_decks", 6, ()),
    BenchmarkScenario("neutral_8_decks", 8, ()),
    BenchmarkScenario(
        "low_cards_removed",
        6,
        tuple(rank for rank in ("2", "3", "4", "5", "6") for _ in range(8)),
    ),
    BenchmarkScenario(
        "high_cards_removed",
        6,
        ("A",) * 8 + ("9",) * 8 + ("10",) * 32,
    ),
    BenchmarkScenario(
        "near_consumed_valid",
        1,
        _near_consumed_seen_cards(),
    ),
)


def run_benchmark() -> None:
    print(
        "scenario | edge | risk_min | bankroll_required | states | "
        "duration_ms | timed_out | warnings"
    )
    for scenario in SCENARIOS:
        result = evaluate_machine_ev_pre_round(
            MachineEvInput(
                number_of_decks=scenario.number_of_decks,
                seen_cards=scenario.seen_cards,
                bankroll=1000,
                minimum_bet=10,
            )
        )
        summary = result.summary
        metrics = result.metrics
        print(
            f"{scenario.name} | "
            f"{summary.estimated_next_hand_edge!r} | "
            f"{summary.risk_if_minimum_bet!r} | "
            f"{summary.minimum_bankroll_required_for_minimum_bet!r} | "
            f"{metrics.states_evaluated} | "
            f"{metrics.duration_ms:.3f} | "
            f"{metrics.timed_out} | "
            f"{'; '.join(metrics.warnings) or '-'}"
        )


if __name__ == "__main__":
    run_benchmark()
