from __future__ import annotations

import importlib.util
import inspect
import math
import sys
from pathlib import Path
from types import ModuleType

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "compare_machine_ev_vs_counting_systems.py"
)


@pytest.fixture(scope="module")
def comparator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "compare_machine_ev_vs_counting_systems",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def neutral_result(comparator: ModuleType) -> dict[str, object]:
    scenario = next(
        scenario
        for scenario in comparator.SCENARIOS
        if scenario.scenario_id == "neutral_6_decks"
    )
    return comparator.run_scenario(scenario)


def _all_keys(value: object):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from _all_keys(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _all_keys(nested)


def _numeric_values(value: object):
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield float(value)
        return
    if isinstance(value, dict):
        for nested in value.values():
            yield from _numeric_values(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _numeric_values(nested)


def test_script_imports_without_running_benchmark(
    comparator: ModuleType,
) -> None:
    assert callable(comparator.main)
    assert callable(comparator.run_scenario)
    assert callable(comparator.classify_machine_ev_count_alignment)


def test_required_scenarios_are_defined_and_valid(
    comparator: ModuleType,
) -> None:
    scenario_ids = {
        scenario.scenario_id
        for scenario in comparator.SCENARIOS
    }
    assert scenario_ids == {
        "neutral_6_decks",
        "low_cards_removed",
        "high_cards_removed",
        "ten_rich_ace_poor",
        "ace_rich_ten_neutral",
        "late_shoe_composition",
        "blackjack_6_to_5",
        "neutral_h17",
        "surrender_allowed",
        "small_bankroll_high_minimum",
    }

    for scenario in comparator.SCENARIOS:
        assert scenario.number_of_decks > 0
        assert isinstance(scenario.seen_cards, tuple)
        assert scenario.bankroll > 0
        assert scenario.minimum_bet > 0
        assert scenario.rules
        assert scenario.label
        comparator.validate_scenario(scenario)
        remaining = comparator.build_machine_ev_shoe_counts(
            scenario.number_of_decks,
            scenario.seen_cards,
        )
        assert sum(remaining.values()) >= 3
        assert all(count >= 0 for count in remaining.values())


def test_smoke_scenario_returns_finite_separated_results(
    neutral_result: dict[str, object],
) -> None:
    assert all(math.isfinite(value) for value in _numeric_values(neutral_result))
    assert "counting_systems" in neutral_result
    assert "machine_ev" in neutral_result
    assert "systems" not in neutral_result

    counting_systems = neutral_result["counting_systems"]
    machine_ev = neutral_result["machine_ev"]
    assert isinstance(counting_systems, dict)
    assert isinstance(machine_ev, dict)
    assert set(counting_systems) == {
        "hi_lo",
        "hi_opt_ii",
        "wong_halves",
    }
    assert machine_ev["model_id"] == "machine_ev"
    assert machine_ev["is_human_replicable"] is False
    assert math.isfinite(machine_ev["estimated_next_hand_edge"])
    assert neutral_result["alignment"] in {
        "aligned_positive",
        "aligned_negative",
        "count_positive_machine_negative",
        "count_negative_machine_positive",
        "mixed_count_signals",
        "neutral_or_low_signal",
    }


@pytest.mark.parametrize(
    ("count_edges", "machine_edge", "expected"),
    [
        (
            {"hi_lo": 0.01, "hi_opt_ii": 0.02, "wong_halves": 0.03},
            0.015,
            "aligned_positive",
        ),
        (
            {"hi_lo": -0.01, "hi_opt_ii": -0.02, "wong_halves": -0.03},
            -0.015,
            "aligned_negative",
        ),
        (
            {"hi_lo": 0.01, "hi_opt_ii": 0.02, "wong_halves": 0.03},
            -0.015,
            "count_positive_machine_negative",
        ),
        (
            {"hi_lo": -0.01, "hi_opt_ii": -0.02, "wong_halves": -0.03},
            0.015,
            "count_negative_machine_positive",
        ),
        (
            {"hi_lo": -0.01, "hi_opt_ii": 0.02, "wong_halves": 0.03},
            0.015,
            "mixed_count_signals",
        ),
        (
            {"hi_lo": 0.0, "hi_opt_ii": 0.0, "wong_halves": 0.0},
            0.0,
            "neutral_or_low_signal",
        ),
    ],
)
def test_alignment_classification(
    comparator: ModuleType,
    count_edges: dict[str, float],
    machine_edge: float,
    expected: str,
) -> None:
    assert comparator.classify_machine_ev_count_alignment(
        count_edges,
        machine_edge,
    ) == expected


def test_benchmark_uses_direct_internal_functions_without_http(
    comparator: ModuleType,
) -> None:
    source = inspect.getsource(comparator)

    assert "TestClient" not in source
    assert "requests" not in source
    assert "httpx" not in source
    assert "client.post" not in source
    assert "analyze_pre_round(" in source
    assert "evaluate_machine_ev_pre_round(" in source


def test_result_does_not_reveal_dealer_hole_card(
    neutral_result: dict[str, object],
) -> None:
    assert "dealer_hole_card" not in set(_all_keys(neutral_result))


def test_output_language_avoids_prohibited_claims(
    comparator: ModuleType,
    neutral_result: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    comparator.print_report([neutral_result])
    output = capsys.readouterr().out.lower()

    for prohibited in (
        "garantido",
        "garantia",
        "aposta segura",
        "vencer o cassino",
        "lucro certo",
        "certeza",
        "infalivel",
        "infalível",
    ):
        assert prohibited not in output


def test_cli_smoke_path_is_callable_without_writing_output(
    comparator: ModuleType,
    neutral_result: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_run(scenarios):
        captured["scenario_ids"] = tuple(
            scenario.scenario_id
            for scenario in scenarios
        )
        return [neutral_result]

    monkeypatch.setattr(comparator, "run_scenarios", fake_run)

    assert comparator.main(["--smoke"]) == 0
    assert captured["scenario_ids"] == comparator.SMOKE_SCENARIO_IDS
    assert "Machine EV vs human counting systems" in capsys.readouterr().out


def test_optional_json_output_writes_only_when_called(
    comparator: ModuleType,
    neutral_result: dict[str, object],
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "machine_ev_vs_counts.json"

    written = comparator.write_output([neutral_result], output_path)

    assert written == output_path
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert '"counting_systems"' in content
    assert '"machine_ev"' in content
