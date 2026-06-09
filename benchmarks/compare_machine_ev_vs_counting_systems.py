from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from blackjack_risk_engine.engine_core.cards import ONE_DECK_COUNTS, RANK_STRINGS
from blackjack_risk_engine.engine_core.pre_round import analyze_pre_round
from blackjack_risk_engine.engine_core.pre_round.machine_ev import (
    MachineEvConfig,
    MachineEvInput,
    build_machine_ev_shoe_counts,
    evaluate_machine_ev_pre_round,
)


Rules = dict[str, object]
BenchmarkResult = dict[str, object]

ALIGNMENT_THRESHOLD = 0.001
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT
    / "benchmarks"
    / "output"
    / "machine_ev_vs_counts.json"
)

STANDARD_RULES: Rules = {
    "blackjack_payout": "3:2",
    "dealer_hits_soft_17": False,
    "double_after_split": True,
    "surrender_allowed": False,
    "dealer_peek": True,
}


@dataclass(frozen=True, slots=True)
class ComparisonScenario:
    scenario_id: str
    label: str
    number_of_decks: int
    seen_cards: tuple[str, ...]
    bankroll: float
    minimum_bet: float
    rules: Rules


def _full_shoe_cards(number_of_decks: int) -> list[str]:
    cards: list[str] = []
    for rank, count in zip(RANK_STRINGS, ONE_DECK_COUNTS, strict=True):
        cards.extend([rank] * count * number_of_decks)
    return cards


def _late_shoe_seen_cards() -> tuple[str, ...]:
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


LOW_CARDS_REMOVED = tuple(
    rank
    for rank in ("2", "3", "4", "5", "6")
    for _ in range(12)
)
HIGH_CARDS_REMOVED = ("A",) * 12 + ("10",) * 48
ACE_RICH_TEN_NEUTRAL = tuple(
    rank
    for rank in ("2", "3", "4", "5", "6", "7", "8", "9")
    for _ in range(4)
) + ("10",) * 16


SCENARIOS: tuple[ComparisonScenario, ...] = (
    ComparisonScenario(
        scenario_id="neutral_6_decks",
        label="Neutral 6 decks",
        number_of_decks=6,
        seen_cards=(),
        bankroll=1000,
        minimum_bet=10,
        rules=STANDARD_RULES,
    ),
    ComparisonScenario(
        scenario_id="low_cards_removed",
        label="Low cards removed",
        number_of_decks=6,
        seen_cards=LOW_CARDS_REMOVED,
        bankroll=1000,
        minimum_bet=10,
        rules=STANDARD_RULES,
    ),
    ComparisonScenario(
        scenario_id="high_cards_removed",
        label="High cards removed",
        number_of_decks=6,
        seen_cards=HIGH_CARDS_REMOVED,
        bankroll=1000,
        minimum_bet=10,
        rules=STANDARD_RULES,
    ),
    ComparisonScenario(
        scenario_id="ten_rich_ace_poor",
        label="Ten-rich but ace-poor",
        number_of_decks=6,
        seen_cards=("A",) * 16,
        bankroll=1000,
        minimum_bet=10,
        rules=STANDARD_RULES,
    ),
    ComparisonScenario(
        scenario_id="ace_rich_ten_neutral",
        label="Ace-rich with near-neutral ten share",
        number_of_decks=6,
        seen_cards=ACE_RICH_TEN_NEUTRAL,
        bankroll=1000,
        minimum_bet=10,
        rules=STANDARD_RULES,
    ),
    ComparisonScenario(
        scenario_id="late_shoe_composition",
        label="Late shoe composition",
        number_of_decks=1,
        seen_cards=_late_shoe_seen_cards(),
        bankroll=1000,
        minimum_bet=10,
        rules=STANDARD_RULES,
    ),
    ComparisonScenario(
        scenario_id="blackjack_6_to_5",
        label="Low cards removed with blackjack 6:5",
        number_of_decks=6,
        seen_cards=LOW_CARDS_REMOVED,
        bankroll=1000,
        minimum_bet=10,
        rules={**STANDARD_RULES, "blackjack_payout": "6:5"},
    ),
    ComparisonScenario(
        scenario_id="neutral_h17",
        label="Neutral 6 decks with H17",
        number_of_decks=6,
        seen_cards=(),
        bankroll=1000,
        minimum_bet=10,
        rules={**STANDARD_RULES, "dealer_hits_soft_17": True},
    ),
    ComparisonScenario(
        scenario_id="surrender_allowed",
        label="Neutral 6 decks with surrender",
        number_of_decks=6,
        seen_cards=(),
        bankroll=1000,
        minimum_bet=10,
        rules={**STANDARD_RULES, "surrender_allowed": True},
    ),
    ComparisonScenario(
        scenario_id="small_bankroll_high_minimum",
        label="Positive composition with small bankroll",
        number_of_decks=6,
        seen_cards=LOW_CARDS_REMOVED,
        bankroll=100,
        minimum_bet=50,
        rules=STANDARD_RULES,
    ),
)

SMOKE_SCENARIO_IDS = ("neutral_6_decks", "ten_rich_ace_poor")


def classify_machine_ev_count_alignment(
    counting_edges: Mapping[str, float],
    machine_ev_edge: float,
    *,
    threshold: float = ALIGNMENT_THRESHOLD,
) -> str:
    if not counting_edges:
        raise ValueError("counting_edges must contain at least one system")
    if not math.isfinite(machine_ev_edge):
        raise ValueError("machine_ev_edge must be finite")
    if not math.isfinite(threshold) or threshold < 0:
        raise ValueError("threshold must be finite and non-negative")

    count_signs = {
        _edge_sign(_finite_float(edge, f"{system_id} edge"), threshold)
        for system_id, edge in counting_edges.items()
    }
    machine_sign = _edge_sign(machine_ev_edge, threshold)

    if "positive" in count_signs and "negative" in count_signs:
        return "mixed_count_signals"
    if machine_sign == "positive" and count_signs <= {"positive", "neutral"}:
        if "positive" in count_signs:
            return "aligned_positive"
    if machine_sign == "negative" and count_signs <= {"negative", "neutral"}:
        if "negative" in count_signs:
            return "aligned_negative"
    if machine_sign == "negative" and count_signs == {"positive"}:
        return "count_positive_machine_negative"
    if machine_sign == "positive" and count_signs == {"negative"}:
        return "count_negative_machine_positive"
    return "neutral_or_low_signal"


def alignment_observation(classification: str) -> str:
    observations = {
        "aligned_positive": (
            "Machine EV and the counting estimates indicate positive direction."
        ),
        "aligned_negative": (
            "Machine EV and the counting estimates indicate negative direction."
        ),
        "count_positive_machine_negative": (
            "Positive count estimates diverge from the composition-based Machine EV."
        ),
        "count_negative_machine_positive": (
            "Negative count estimates diverge from the composition-based Machine EV."
        ),
        "mixed_count_signals": (
            "The human counting estimates have mixed directional signals."
        ),
        "neutral_or_low_signal": (
            "At least one signal is neutral or below the comparison threshold."
        ),
    }
    try:
        return observations[classification]
    except KeyError as error:
        raise ValueError(f"unknown alignment classification: {classification}") from error


def validate_scenario(scenario: ComparisonScenario) -> None:
    if not scenario.scenario_id or not scenario.label:
        raise ValueError("scenario id and label must not be empty")
    if scenario.bankroll <= 0 or not math.isfinite(scenario.bankroll):
        raise ValueError("scenario bankroll must be positive and finite")
    if scenario.minimum_bet <= 0 or not math.isfinite(scenario.minimum_bet):
        raise ValueError("scenario minimum_bet must be positive and finite")

    counts = build_machine_ev_shoe_counts(
        scenario.number_of_decks,
        scenario.seen_cards,
    )
    if sum(counts.values()) < 3:
        raise ValueError("scenario must leave at least three cards in the shoe")


def run_scenario(scenario: ComparisonScenario) -> BenchmarkResult:
    validate_scenario(scenario)
    rules = dict(scenario.rules)
    seen_cards = tuple(scenario.seen_cards)

    human_analysis = analyze_pre_round(
        number_of_decks=scenario.number_of_decks,
        seen_cards=seen_cards,
        bankroll=scenario.bankroll,
        minimum_bet=scenario.minimum_bet,
        rules=rules,
    )
    machine_result = evaluate_machine_ev_pre_round(
        MachineEvInput(
            number_of_decks=scenario.number_of_decks,
            seen_cards=seen_cards,
            bankroll=scenario.bankroll,
            minimum_bet=scenario.minimum_bet,
            rules=rules,
        ),
        MachineEvConfig(
            decision_engine_mode="hybrid",
            include_debug_metrics=True,
            max_duration_ms=2000,
            use_cache=True,
        ),
    )

    counting_systems = _extract_counting_systems(human_analysis)
    machine_edge = _finite_float(
        machine_result.summary.estimated_next_hand_edge,
        "Machine EV edge",
    )
    classification = classify_machine_ev_count_alignment(
        {
            system_id: _finite_float(
                system["estimated_edge"],
                f"{system_id} estimated edge",
            )
            for system_id, system in counting_systems.items()
        },
        machine_edge,
    )
    duration_ms = _finite_float(
        machine_result.metrics.duration_ms,
        "Machine EV duration_ms",
    )

    result: BenchmarkResult = {
        "scenario_id": scenario.scenario_id,
        "scenario_label": scenario.label,
        "number_of_decks": scenario.number_of_decks,
        "cards_seen_count": len(seen_cards),
        "rules_summary": make_rules_summary(rules),
        "counting_systems": counting_systems,
        "machine_ev": {
            "model_id": machine_result.summary.model_id,
            "model_type": machine_result.summary.model_type,
            "is_human_replicable": machine_result.summary.is_human_replicable,
            "estimated_next_hand_edge": machine_edge,
            "risk_if_minimum_bet": machine_result.summary.risk_if_minimum_bet,
            "minimum_bankroll_required_for_minimum_bet": (
                machine_result.summary.minimum_bankroll_required_for_minimum_bet
            ),
            "recommendation_status": (
                machine_result.summary.recommendation_status
            ),
            "states_evaluated": machine_result.metrics.states_evaluated,
            "duration_ms": duration_ms,
            "timed_out": machine_result.metrics.timed_out,
            "warnings": list(machine_result.metrics.warnings),
        },
        "alignment": classification,
        "observation": alignment_observation(classification),
    }
    assert_finite_result(result)
    return result


def run_scenarios(
    scenarios: Iterable[ComparisonScenario] = SCENARIOS,
) -> list[BenchmarkResult]:
    return [run_scenario(scenario) for scenario in scenarios]


def make_rules_summary(rules: Mapping[str, object]) -> str:
    return ", ".join(
        (
            f"BJ {rules.get('blackjack_payout', '3:2')}",
            "H17" if rules.get("dealer_hits_soft_17", False) else "S17",
            (
                "surrender"
                if rules.get("surrender_allowed", False)
                else "no surrender"
            ),
            (
                "DAS"
                if rules.get("double_after_split", True)
                else "no DAS"
            ),
        )
    )


def assert_finite_result(result: BenchmarkResult) -> None:
    for value in _iter_numeric_values(result):
        if not math.isfinite(value):
            raise RuntimeError("benchmark produced a non-finite numeric value")


def print_report(results: Sequence[BenchmarkResult]) -> None:
    comparison_headers = (
        "scenario",
        "label",
        "decks",
        "seen",
        "rules",
        "Hi-Lo TC",
        "Hi-Lo edge",
        "Hi-Opt BTC",
        "Hi-Opt edge",
        "Wong TC",
        "Wong edge",
        "Machine EV",
        "alignment",
    )
    comparison_rows = []
    diagnostic_rows = []
    for result in results:
        systems = result["counting_systems"]
        machine = result["machine_ev"]
        if not isinstance(systems, dict) or not isinstance(machine, dict):
            raise RuntimeError("invalid benchmark result structure")
        hi_lo = systems["hi_lo"]
        hi_opt_ii = systems["hi_opt_ii"]
        wong_halves = systems["wong_halves"]
        comparison_rows.append(
            (
                result["scenario_id"],
                result["scenario_label"],
                result["number_of_decks"],
                result["cards_seen_count"],
                result["rules_summary"],
                _signed(hi_lo["true_count"]),
                _percent(hi_lo["estimated_edge"]),
                _signed(hi_opt_ii["betting_true_count"]),
                _percent(hi_opt_ii["estimated_edge"]),
                _signed(wong_halves["true_count"]),
                _percent(wong_halves["estimated_edge"]),
                _percent(machine["estimated_next_hand_edge"]),
                result["alignment"],
            )
        )
        diagnostic_rows.append(
            (
                result["scenario_id"],
                _optional_percent(machine["risk_if_minimum_bet"]),
                _optional_number(
                    machine["minimum_bankroll_required_for_minimum_bet"]
                ),
                f"{float(machine['duration_ms']):.2f}",
                str(machine["timed_out"]),
                result["observation"],
            )
        )

    print("Machine EV vs human counting systems")
    print(_render_table(comparison_headers, comparison_rows))
    print()
    print("Machine EV risk and performance diagnostics")
    print(
        _render_table(
            (
                "scenario",
                "risk at min",
                "bankroll required",
                "duration ms",
                "timed out",
                "observation",
            ),
            diagnostic_rows,
        )
    )
    print()
    print(
        "Human counts are compressed proxies; Machine EV uses full shoe composition."
    )
    print(f"Scenarios executed: {len(results)}")


def write_output(
    results: Sequence[BenchmarkResult],
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(list(results), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare composition-based Machine EV with human counting estimates."
        )
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run two representative scenarios instead of the full benchmark.",
    )
    parser.add_argument(
        "--write-output",
        action="store_true",
        help="Write JSON output under benchmarks/output.",
    )
    args = parser.parse_args(argv)

    selected = (
        tuple(
            scenario
            for scenario in SCENARIOS
            if scenario.scenario_id in SMOKE_SCENARIO_IDS
        )
        if args.smoke
        else SCENARIOS
    )
    results = run_scenarios(selected)
    print_report(results)
    if args.write_output:
        output_path = write_output(results)
        print(f"JSON output: {output_path}")
    return 0


def _extract_counting_systems(
    analysis: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    systems = analysis.get("systems")
    if not isinstance(systems, list):
        raise RuntimeError("pre-round analysis systems must be a list")

    extracted: dict[str, dict[str, object]] = {}
    for system in systems:
        if not isinstance(system, Mapping):
            raise RuntimeError("counting system result must be a mapping")
        system_id = system.get("system_id")
        if system_id not in {"hi_lo", "hi_opt_ii", "wong_halves"}:
            raise RuntimeError(f"unexpected counting system: {system_id!r}")
        extracted[str(system_id)] = {
            "label": system["label"],
            "true_count": _finite_float(
                system["true_count"],
                f"{system_id} true count",
            ),
            "betting_true_count": _finite_float(
                system["betting_true_count"],
                f"{system_id} betting true count",
            ),
            "estimated_edge": _finite_float(
                system["estimated_player_edge"],
                f"{system_id} estimated edge",
            ),
        }

    expected_ids = {"hi_lo", "hi_opt_ii", "wong_halves"}
    if set(extracted) != expected_ids:
        raise RuntimeError("benchmark requires all three human counting systems")
    return extracted


def _edge_sign(edge: float, threshold: float) -> str:
    if edge > threshold:
        return "positive"
    if edge < -threshold:
        return "negative"
    return "neutral"


def _finite_float(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{label} must be a finite number")
    return converted


def _iter_numeric_values(value: object):
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield float(value)
        return
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _iter_numeric_values(nested)
        return
    if isinstance(value, (list, tuple)):
        for nested in value:
            yield from _iter_numeric_values(nested)


def _signed(value: object) -> str:
    return f"{float(value):+.2f}"


def _percent(value: object) -> str:
    return f"{float(value) * 100:+.2f}%"


def _optional_percent(value: object) -> str:
    return "-" if value is None else f"{float(value) * 100:.2f}%"


def _optional_number(value: object) -> str:
    return "-" if value is None else f"{float(value):.2f}"


def _render_table(
    headers: Sequence[object],
    rows: Sequence[Sequence[object]],
) -> str:
    string_rows = [tuple(str(cell) for cell in row) for row in rows]
    widths = [
        max(
            len(str(header)),
            *(len(row[index]) for row in string_rows),
        )
        for index, header in enumerate(headers)
    ]

    def render_row(row: Sequence[object]) -> str:
        return " | ".join(
            str(cell).ljust(widths[index])
            for index, cell in enumerate(row)
        )

    separator = "-+-".join("-" * width for width in widths)
    return "\n".join(
        (
            render_row(headers),
            separator,
            *(render_row(row) for row in string_rows),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
