from __future__ import annotations

import importlib.util
import inspect
import math
import sys
from dataclasses import asdict, fields
from pathlib import Path
from types import ModuleType

import pytest

from blackjack_risk_engine.engine_core.cards import ONE_DECK_COUNTS, RANK_STRINGS
from blackjack_risk_engine.engine_core.pre_round.machine_ev import (
    MachineEvConfig,
    MachineEvInput,
    MachineEvPublicSummary,
    MachineEvResult,
    MachineEvStateEvaluation,
    build_machine_ev_shoe_counts,
    enumerate_observable_initial_states,
    evaluate_machine_ev_pre_round,
)
import blackjack_risk_engine.engine_core.pre_round.machine_ev.evaluator as evaluator_module


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPARATOR_PATH = (
    PROJECT_ROOT
    / "benchmarks"
    / "compare_machine_ev_vs_counting_systems.py"
)
AUDIT_SCRIPT_PATH = (
    PROJECT_ROOT
    / "benchmarks"
    / "audit_machine_ev_accuracy.py"
)

AUDITED_SCENARIO_IDS = (
    "neutral_6_decks",
    "low_cards_removed",
    "high_cards_removed",
    "late_shoe_composition",
    "blackjack_6_to_5",
    "neutral_h17",
    "surrender_allowed",
    "small_bankroll_high_minimum",
)


def _load_script(module_name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def comparator() -> ModuleType:
    return _load_script("machine_ev_accuracy_comparator", COMPARATOR_PATH)


@pytest.fixture(scope="module")
def audit_script() -> ModuleType:
    benchmark_dir = str(PROJECT_ROOT / "benchmarks")
    if benchmark_dir not in sys.path:
        sys.path.insert(0, benchmark_dir)
    return _load_script("machine_ev_accuracy_script", AUDIT_SCRIPT_PATH)


@pytest.fixture(scope="module")
def audited_results(
    comparator: ModuleType,
) -> dict[str, dict[str, object]]:
    scenarios = {
        scenario.scenario_id: scenario
        for scenario in comparator.SCENARIOS
    }
    return {
        scenario_id: comparator.run_scenario(scenarios[scenario_id])
        for scenario_id in AUDITED_SCENARIO_IDS
    }


@pytest.fixture(scope="module")
def missing_wager_result(comparator: ModuleType) -> MachineEvResult:
    scenario = next(
        scenario
        for scenario in comparator.SCENARIOS
        if scenario.scenario_id == "low_cards_removed"
    )
    return evaluate_machine_ev_pre_round(
        MachineEvInput(
            number_of_decks=scenario.number_of_decks,
            seen_cards=scenario.seen_cards,
            bankroll=None,
            minimum_bet=scenario.minimum_bet,
            rules=dict(scenario.rules),
        ),
        MachineEvConfig(),
    )


def _machine(result: dict[str, object]) -> dict[str, object]:
    machine = result["machine_ev"]
    assert isinstance(machine, dict)
    return machine


def _edge(result: dict[str, object]) -> float:
    return float(_machine(result)["estimated_next_hand_edge"])


def _all_keys(value: object):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from _all_keys(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _all_keys(nested)


def test_all_controlled_scenarios_satisfy_numeric_invariants(
    audited_results: dict[str, dict[str, object]],
) -> None:
    for result in audited_results.values():
        machine = _machine(result)
        edge = float(machine["estimated_next_hand_edge"])
        duration_ms = float(machine["duration_ms"])
        risk = machine["risk_if_minimum_bet"]
        required_bankroll = machine[
            "minimum_bankroll_required_for_minimum_bet"
        ]

        assert math.isfinite(edge)
        assert -0.20 <= edge <= 0.20
        assert math.isfinite(duration_ms)
        assert duration_ms >= 0
        assert machine["states_evaluated"] > 0
        if risk is not None:
            assert math.isfinite(risk)
            assert 0 <= risk <= 1
        if required_bankroll is not None:
            assert math.isfinite(required_bankroll)
            assert required_bankroll > 0


def test_neutral_six_deck_result_is_finite_and_plausible(
    audited_results: dict[str, dict[str, object]],
) -> None:
    edge = _edge(audited_results["neutral_6_decks"])

    assert math.isfinite(edge)
    assert -0.20 <= edge <= 0.20


def test_favorable_and_unfavorable_compositions_have_expected_direction(
    audited_results: dict[str, dict[str, object]],
) -> None:
    low_cards_removed = _edge(audited_results["low_cards_removed"])
    high_cards_removed = _edge(audited_results["high_cards_removed"])

    assert low_cards_removed > high_cards_removed


def test_blackjack_six_to_five_does_not_improve_player_ev(
    audited_results: dict[str, dict[str, object]],
) -> None:
    three_to_two = _edge(audited_results["low_cards_removed"])
    six_to_five = _edge(audited_results["blackjack_6_to_5"])

    assert six_to_five <= three_to_two + 1e-9


def test_h17_does_not_improve_player_ev_over_s17(
    audited_results: dict[str, dict[str, object]],
) -> None:
    s17 = _edge(audited_results["neutral_6_decks"])
    h17 = _edge(audited_results["neutral_h17"])

    assert h17 <= s17 + 1e-9


def test_surrender_does_not_reduce_player_ev(
    audited_results: dict[str, dict[str, object]],
) -> None:
    without_surrender = _edge(audited_results["neutral_6_decks"])
    with_surrender = _edge(audited_results["surrender_allowed"])

    assert with_surrender + 1e-9 >= without_surrender


def test_late_shoe_remains_finite_and_valid(
    comparator: ModuleType,
    audited_results: dict[str, dict[str, object]],
) -> None:
    scenario = next(
        scenario
        for scenario in comparator.SCENARIOS
        if scenario.scenario_id == "late_shoe_composition"
    )
    remaining = build_machine_ev_shoe_counts(
        scenario.number_of_decks,
        scenario.seen_cards,
    )

    assert sum(remaining.values()) >= 3
    assert all(count >= 0 for count in remaining.values())
    assert math.isfinite(_edge(audited_results[scenario.scenario_id]))


def test_small_bankroll_high_minimum_reports_high_risk_without_bet_suggestion(
    audited_results: dict[str, dict[str, object]],
) -> None:
    machine = _machine(audited_results["small_bankroll_high_minimum"])

    assert machine["risk_if_minimum_bet"] > 0.5
    assert machine["minimum_bankroll_required_for_minimum_bet"] > 100
    assert "suggested_units" not in machine
    assert "suggested_amount" not in machine


def test_non_positive_edge_has_no_finite_required_bankroll(
    audited_results: dict[str, dict[str, object]],
) -> None:
    machine = _machine(audited_results["high_cards_removed"])

    assert machine["estimated_next_hand_edge"] < 0
    assert machine["risk_if_minimum_bet"] == 1.0
    assert machine["minimum_bankroll_required_for_minimum_bet"] is None
    assert machine["recommendation_status"] == "machine_ev_non_positive_edge"


def test_missing_bankroll_still_calculates_edge_and_required_bankroll(
    missing_wager_result: MachineEvResult,
) -> None:
    summary = missing_wager_result.summary

    assert math.isfinite(summary.estimated_next_hand_edge)
    assert summary.risk_if_minimum_bet is None
    assert math.isfinite(
        summary.minimum_bankroll_required_for_minimum_bet
    )
    assert summary.recommendation_status == (
        "machine_ev_missing_wager_inputs"
    )


def test_same_input_and_config_are_deterministic(
    comparator: ModuleType,
    audited_results: dict[str, dict[str, object]],
) -> None:
    scenario = next(
        scenario
        for scenario in comparator.SCENARIOS
        if scenario.scenario_id == "late_shoe_composition"
    )
    repeated = evaluate_machine_ev_pre_round(
        MachineEvInput(
            number_of_decks=scenario.number_of_decks,
            seen_cards=scenario.seen_cards,
            bankroll=scenario.bankroll,
            minimum_bet=scenario.minimum_bet,
            rules=dict(scenario.rules),
        ),
        MachineEvConfig(
            decision_engine_mode="hybrid",
            include_debug_metrics=True,
            max_duration_ms=2000,
            use_cache=True,
        ),
    )
    first = _machine(audited_results[scenario.scenario_id])

    assert repeated.summary.estimated_next_hand_edge == pytest.approx(
        first["estimated_next_hand_edge"],
        abs=1e-12,
    )
    assert repeated.summary.risk_if_minimum_bet == pytest.approx(
        first["risk_if_minimum_bet"],
        abs=1e-12,
    )
    assert repeated.summary.minimum_bankroll_required_for_minimum_bet == (
        first["minimum_bankroll_required_for_minimum_bet"]
    )
    assert repeated.summary.recommendation_status == (
        first["recommendation_status"]
    )


def test_benchmark_run_does_not_mutate_scenario_inputs(
    comparator: ModuleType,
    audited_results: dict[str, dict[str, object]],
) -> None:
    scenario = next(
        scenario
        for scenario in comparator.SCENARIOS
        if scenario.scenario_id == "low_cards_removed"
    )

    assert scenario.seen_cards == comparator.LOW_CARDS_REMOVED
    assert scenario.rules == comparator.STANDARD_RULES
    assert audited_results[scenario.scenario_id]["cards_seen_count"] == len(
        comparator.LOW_CARDS_REMOVED
    )


def test_enumerator_removes_seen_and_observable_cards_exactly_once() -> None:
    seen_cards = ("A", "2", "3", "10")
    shoe_counts = build_machine_ev_shoe_counts(1, seen_cards)
    original_counts = shoe_counts.copy()
    states = enumerate_observable_initial_states(shoe_counts)
    expected_total = 52 - len(seen_cards) - 3

    assert sum(state.probability for state in states) == pytest.approx(1.0)
    for state in states:
        expected = original_counts.copy()
        for card in (*state.player_cards, state.dealer_upcard):
            expected[card] -= 1
        assert dict(state.shoe_after) == expected
        assert sum(dict(state.shoe_after).values()) == expected_total
        assert all(count >= 0 for count in dict(state.shoe_after).values())
    assert shoe_counts == original_counts


def test_adapter_propagates_rules_engine_mode_and_exact_shoe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_cards = ("2",)
    state = next(
        item
        for item in enumerate_observable_initial_states(
            build_machine_ev_shoe_counts(1, seen_cards),
        )
        if item.player_cards == ("A", "10")
        and item.dealer_upcard == "6"
    )
    captured: dict[str, object] = {}

    def fake_action_evs(**kwargs: object) -> tuple[tuple[str, float], ...]:
        captured.update(kwargs)
        return (("stand", 0.25),)

    monkeypatch.setattr(
        evaluator_module,
        "_evaluate_action_evs",
        fake_action_evs,
    )
    evaluation = evaluator_module.evaluate_initial_state_with_decision_engine(
        state,
        MachineEvInput(
            number_of_decks=1,
            seen_cards=seen_cards,
            rules={
                "blackjack_payout": "6:5",
                "dealer_hits_soft_17": True,
                "surrender_allowed": True,
                "double_after_split": False,
            },
        ),
        MachineEvConfig(decision_engine_mode="hybrid"),
    )

    core_state = captured["state"]
    active_rules = captured["active_rules"]
    assert captured["mode"] == "hybrid"
    assert core_state.deck_counts == tuple(
        count
        for _, count in state.shoe_after
    )
    assert active_rules.blackjack_payout == "6:5"
    assert active_rules.dealer_hits_soft_17 is True
    assert active_rules.surrender_allowed is True
    assert active_rules.double_after_split is False
    assert not hasattr(core_state, "dealer_hole_card")
    assert evaluation.state_ev == 0.25


def test_models_expose_no_hole_card_human_counts_or_bet_suggestions(
    missing_wager_result: MachineEvResult,
) -> None:
    summary_fields = {field.name for field in fields(MachineEvPublicSummary)}
    result_keys = set(_all_keys(asdict(missing_wager_result)))

    assert "dealer_hole_card" not in result_keys
    assert summary_fields.isdisjoint(
        {
            "running_count",
            "true_count",
            "betting_true_count",
            "ace_side_count",
            "scaled_running_count",
            "suggested_units",
            "suggested_amount",
        }
    )


def test_accuracy_audit_script_imports_without_http_or_automatic_run(
    audit_script: ModuleType,
) -> None:
    source = inspect.getsource(audit_script)

    assert callable(audit_script.main)
    assert callable(audit_script.run_accuracy_audit)
    assert "TestClient" not in source
    assert "requests" not in source
    assert "httpx" not in source
    assert "client.post" not in source


def test_accuracy_audit_cli_smoke_path(
    audit_script: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scenario_audit = {
        "scenario_id": "neutral_6_decks",
        "edge": 0.0,
        "risk_if_minimum_bet": None,
        "minimum_bankroll_required_for_minimum_bet": None,
        "recommendation_status": "machine_ev_missing_wager_inputs",
        "checks": {"edge_finite": True},
        "passed": True,
    }
    direction_audit = {
        "check_id": "low_cards_ev_above_high_cards_ev",
        "left": 0.01,
        "right": -0.01,
        "passed": True,
    }
    monkeypatch.setattr(
        audit_script,
        "run_accuracy_audit",
        lambda scenarios: ([scenario_audit], [direction_audit]),
    )

    assert audit_script.main(["--smoke"]) == 0
    output = capsys.readouterr().out
    assert "Machine EV accuracy audit" in output
    assert "Overall: PASS" in output


def test_accuracy_audit_output_avoids_prohibited_claims(
    audit_script: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    audit_script.print_audit_report(
        [
            {
                "scenario_id": "neutral_6_decks",
                "edge": 0.0,
                "risk_if_minimum_bet": None,
                "minimum_bankroll_required_for_minimum_bet": None,
                "recommendation_status": "machine_ev_missing_wager_inputs",
                "checks": {"edge_finite": True},
                "passed": True,
            }
        ],
        [],
    )
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
