import math
import unittest
from functools import lru_cache
from typing import NamedTuple

from blackjack_risk_engine.decisions import Decision, get_legal_actions
from blackjack_risk_engine.engine_core.action_ev import (
    calculate_action_evs_deterministic,
    ev_blackjack_stand,
    ev_double,
    ev_hit,
    ev_stand,
    ev_surrender,
)
from blackjack_risk_engine.engine_core.adapters import build_core_state_from_inputs
from blackjack_risk_engine.engine_core.cards import deck_counts_for_decks, string_to_rank
from blackjack_risk_engine.engine_core.dealer_dp import (
    dealer_distribution_to_dict,
    dealer_natural_blackjack_probability,
    dealer_outcome_distribution,
    natural_blackjack_stand_ev,
    stand_ev_from_distribution,
)
from blackjack_risk_engine.engine_core.hand import evaluate_hand_from_ranks
from blackjack_risk_engine.engine_core.rules import CoreRules
from blackjack_risk_engine.ev import analyze_hand
from blackjack_risk_engine.hand import Hand
from blackjack_risk_engine.rules import GameRules


RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10")
RANK_TO_INDEX = {rank: index for index, rank in enumerate(RANKS)}
RANK_VALUES = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
DEALER_TOTALS = (17, 18, 19, 20, 21)


class OracleStats(NamedTuple):
    expected_value: float
    win_rate: float
    lose_rate: float
    push_rate: float
    second_moment: float


def ranks(cards: list[str]) -> tuple[int, ...]:
    return tuple(string_to_rank(card) for card in cards)


def counts_from_cards(cards: list[str]) -> tuple[int, ...]:
    counts = [0] * len(RANKS)
    for card in cards:
        counts[RANK_TO_INDEX[card]] += 1
    return tuple(counts)


def action_evs_by_name(result: dict) -> dict[str, float]:
    return {action["action"]: action["ev"] for action in result["actions"]}


def assert_probability_distribution(test: unittest.TestCase, distribution: tuple[float, ...]) -> None:
    test.assertAlmostEqual(sum(distribution), 1.0, places=12)
    for probability in distribution:
        test.assertGreaterEqual(probability, 0.0)
        test.assertLessEqual(probability, 1.0)
        test.assertTrue(math.isfinite(probability))


def oracle_add_card(total: int, soft_aces: int, rank: int) -> tuple[int, int]:
    total += 11 if rank == RANK_TO_INDEX["A"] else RANK_VALUES[rank]
    if rank == RANK_TO_INDEX["A"]:
        soft_aces += 1

    while total > 21 and soft_aces:
        total -= 10
        soft_aces -= 1

    return total, soft_aces


def oracle_dealer_distribution(
    dealer_upcard_rank: int,
    deck_counts: tuple[int, ...],
    dealer_hits_soft_17: bool,
) -> tuple[float, float, float, float, float, float]:
    total, soft_aces = oracle_add_card(0, 0, dealer_upcard_rank)
    return oracle_dealer_distribution_from_state(total, soft_aces, deck_counts, dealer_hits_soft_17)


@lru_cache(maxsize=None)
def oracle_dealer_distribution_from_state(
    total: int,
    soft_aces: int,
    deck_counts: tuple[int, ...],
    dealer_hits_soft_17: bool,
) -> tuple[float, float, float, float, float, float]:
    if total > 21:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    if total >= 17 and not (total == 17 and soft_aces > 0 and dealer_hits_soft_17):
        values = [0.0] * 6
        values[total - 17] = 1.0
        return tuple(values)  # type: ignore[return-value]

    remaining = sum(deck_counts)
    if remaining <= 0:
        raise AssertionError(f"oracle dealer exhausted before terminal total: {total}")

    weighted = [0.0] * 6
    for rank, count in enumerate(deck_counts):
        if count <= 0:
            continue
        next_counts = list(deck_counts)
        next_counts[rank] -= 1
        next_total, next_soft_aces = oracle_add_card(total, soft_aces, rank)
        branch = oracle_dealer_distribution_from_state(
            next_total,
            next_soft_aces,
            tuple(next_counts),
            dealer_hits_soft_17,
        )
        probability = count / remaining
        for index, value in enumerate(branch):
            weighted[index] += probability * value
    return tuple(weighted)  # type: ignore[return-value]


def oracle_dealer_natural_blackjack_probability(dealer_upcard_rank: int, deck_counts: tuple[int, ...]) -> float:
    remaining = sum(deck_counts)
    if dealer_upcard_rank == RANK_TO_INDEX["A"]:
        return deck_counts[RANK_TO_INDEX["10"]] / remaining
    if dealer_upcard_rank == RANK_TO_INDEX["10"]:
        return deck_counts[RANK_TO_INDEX["A"]] / remaining
    return 0.0


def oracle_stand_ev(
    player_total: int,
    dealer_upcard_rank: int,
    deck_counts: tuple[int, ...],
    rules: CoreRules,
) -> OracleStats:
    if player_total > 21:
        return OracleStats(-1.0, 0.0, 1.0, 0.0, 1.0)

    distribution = oracle_dealer_distribution(dealer_upcard_rank, deck_counts, rules.dealer_hits_soft_17)
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

    if player_total == 21:
        dealer_natural = min(
            push_rate,
            oracle_dealer_natural_blackjack_probability(dealer_upcard_rank, deck_counts),
        )
        lose_rate += dealer_natural
        push_rate -= dealer_natural

    expected_value = win_rate - lose_rate
    return OracleStats(expected_value, win_rate, lose_rate, push_rate, win_rate + lose_rate)


def oracle_scale(stats: OracleStats, multiplier: float) -> OracleStats:
    return OracleStats(
        stats.expected_value * multiplier,
        stats.win_rate,
        stats.lose_rate,
        stats.push_rate,
        stats.second_moment * multiplier * multiplier,
    )


def oracle_weighted(base: OracleStats, branch: OracleStats, weight: float) -> OracleStats:
    return OracleStats(
        base.expected_value + branch.expected_value * weight,
        base.win_rate + branch.win_rate * weight,
        base.lose_rate + branch.lose_rate * weight,
        base.push_rate + branch.push_rate * weight,
        base.second_moment + branch.second_moment * weight,
    )


def oracle_loss(outcome: float) -> OracleStats:
    return OracleStats(outcome, 0.0, 1.0, 0.0, outcome * outcome)


def oracle_double_ev(
    player_total: int,
    soft_aces: int,
    dealer_upcard_rank: int,
    deck_counts: tuple[int, ...],
    rules: CoreRules,
) -> OracleStats:
    remaining = sum(deck_counts)
    weighted = OracleStats(0.0, 0.0, 0.0, 0.0, 0.0)
    for rank, count in enumerate(deck_counts):
        if count <= 0:
            continue
        next_counts = list(deck_counts)
        next_counts[rank] -= 1
        next_total, _next_soft_aces = oracle_add_card(player_total, soft_aces, rank)
        branch = (
            oracle_loss(-2.0)
            if next_total > 21
            else oracle_scale(oracle_stand_ev(next_total, dealer_upcard_rank, tuple(next_counts), rules), 2.0)
        )
        weighted = oracle_weighted(weighted, branch, count / remaining)

    dealer_natural = oracle_dealer_natural_blackjack_probability(dealer_upcard_rank, deck_counts)
    return OracleStats(
        weighted.expected_value + dealer_natural,
        weighted.win_rate,
        weighted.lose_rate,
        weighted.push_rate,
        weighted.second_moment - 3.0 * dealer_natural,
    )


@lru_cache(maxsize=None)
def oracle_hit_ev_cached(
    player_total: int,
    soft_aces: int,
    dealer_upcard_rank: int,
    deck_counts: tuple[int, ...],
    dealer_hits_soft_17: bool,
) -> OracleStats:
    rules = CoreRules(dealer_hits_soft_17=dealer_hits_soft_17)
    remaining = sum(deck_counts)
    if remaining <= 0:
        return oracle_stand_ev(player_total, dealer_upcard_rank, deck_counts, rules)

    weighted = OracleStats(0.0, 0.0, 0.0, 0.0, 0.0)
    for rank, count in enumerate(deck_counts):
        if count <= 0:
            continue
        next_counts = list(deck_counts)
        next_counts[rank] -= 1
        next_total, next_soft_aces = oracle_add_card(player_total, soft_aces, rank)
        if next_total > 21:
            branch = oracle_loss(-1.0)
        else:
            stand = oracle_stand_ev(next_total, dealer_upcard_rank, tuple(next_counts), rules)
            hit = oracle_hit_ev_cached(
                next_total,
                next_soft_aces,
                dealer_upcard_rank,
                tuple(next_counts),
                dealer_hits_soft_17,
            )
            branch = hit if hit.expected_value > stand.expected_value else stand
        weighted = oracle_weighted(weighted, branch, count / remaining)
    return weighted


class HandAccuracyTests(unittest.TestCase):
    def test_required_hand_evaluations(self) -> None:
        cases = (
            (["10", "6"], 16, False, False, False),
            (["A", "7"], 18, True, False, False),
            (["A", "7", "10"], 18, False, False, False),
            (["A", "A", "9"], 21, True, False, False),
            (["A", "A", "9", "10"], 21, False, False, False),
            (["10", "9", "5"], 24, False, True, False),
            (["A", "10"], 21, True, False, True),
            (["A", "10", "10"], 21, False, False, False),
            (["A", "5", "5"], 21, True, False, False),
        )

        for cards, total, is_soft, is_bust, is_blackjack in cases:
            with self.subTest(cards=cards):
                evaluation = evaluate_hand_from_ranks(ranks(cards))
                public_hand = Hand.from_values(cards)

                self.assertEqual(evaluation.total, total)
                self.assertEqual(evaluation.is_soft, is_soft)
                self.assertEqual(evaluation.is_bust, is_bust)
                self.assertEqual(evaluation.is_blackjack, is_blackjack)
                self.assertEqual(public_hand.total, total)
                self.assertEqual(public_hand.is_blackjack, is_blackjack)

    def test_invalid_zero_card_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid blackjack card"):
            Hand.from_values(["A", "10", "0"])

    def test_soft_hand_specific_cases_from_stage_22_10(self) -> None:
        cases = (
            (["A", "6"], 17, True),
            (["A", "6", "10"], 17, False),
            (["A", "7"], 18, True),
            (["A", "7", "10"], 18, False),
            (["A", "9"], 20, True),
            (["A", "9", "A"], 21, True),
        )

        for cards, total, is_soft in cases:
            with self.subTest(cards=cards):
                evaluation = evaluate_hand_from_ranks(ranks(cards))

                self.assertEqual(evaluation.total, total)
                self.assertEqual(evaluation.is_soft, is_soft)
                self.assertFalse(evaluation.is_blackjack)


class DealerDpAccuracyTests(unittest.TestCase):
    def test_dealer_soft_17_rule_matches_independent_oracle(self) -> None:
        upcard = string_to_rank("A")
        counts = counts_from_cards(["2", "6", "10"])

        stand_soft_17 = dealer_outcome_distribution(upcard, counts, dealer_hits_soft_17=False)
        hit_soft_17 = dealer_outcome_distribution(upcard, counts, dealer_hits_soft_17=True)

        self.assertEqual(stand_soft_17, oracle_dealer_distribution(upcard, counts, False))
        self.assertEqual(hit_soft_17, oracle_dealer_distribution(upcard, counts, True))
        self.assertAlmostEqual(stand_soft_17[0], 1 / 3)
        self.assertAlmostEqual(hit_soft_17[0], 1 / 6)

    def test_dealer_stands_on_hard_17_and_draws_from_16(self) -> None:
        upcard = string_to_rank("10")

        hard_17_distribution = dealer_outcome_distribution(
            upcard,
            counts_from_cards(["7", "8", "9"]),
            dealer_hits_soft_17=False,
        )
        self.assertAlmostEqual(hard_17_distribution[0], 1 / 3)
        self.assertAlmostEqual(hard_17_distribution[1], 1 / 3)
        self.assertAlmostEqual(hard_17_distribution[2], 1 / 3)

        draw_16_distribution = dealer_outcome_distribution(
            upcard,
            counts_from_cards(["6", "10"]),
            dealer_hits_soft_17=False,
        )
        self.assertAlmostEqual(draw_16_distribution[3], 0.5)
        self.assertAlmostEqual(draw_16_distribution[5], 0.5)

    def test_dealer_distribution_invariants_and_valid_result_keys(self) -> None:
        state = build_core_state_from_inputs(["10", "6"], "9", ["2", "3", "4"], GameRules(number_of_decks=1))

        first = dealer_outcome_distribution(state.dealer_upcard_rank, state.deck_counts, False)
        second = dealer_outcome_distribution(state.dealer_upcard_rank, state.deck_counts, False)

        self.assertEqual(first, second)
        assert_probability_distribution(self, first)
        self.assertEqual(set(dealer_distribution_to_dict(first)), {17, 18, 19, 20, 21, "bust"})
        self.assertGreaterEqual(first[5], 0.0)
        self.assertLessEqual(first[5], 1.0)


class StandEvAccuracyTests(unittest.TestCase):
    def test_stand_ev_direct_outcomes_and_formula(self) -> None:
        rules = CoreRules()
        upcard = string_to_rank("10")

        self.assertEqual(ev_stand(24, upcard, counts_from_cards(["10"]), rules).expected_value, -1.0)
        self.assertEqual(ev_stand(17, upcard, counts_from_cards(["10"]), rules).expected_value, -1.0)
        self.assertEqual(ev_stand(20, upcard, counts_from_cards(["10"]), rules).expected_value, 0.0)

        formula = stand_ev_from_distribution(20, (0.1, 0.1, 0.1, 0.2, 0.1, 0.4))
        self.assertAlmostEqual(formula.win_rate, 0.7)
        self.assertAlmostEqual(formula.lose_rate, 0.1)
        self.assertAlmostEqual(formula.push_rate, 0.2)
        self.assertAlmostEqual(formula.expected_value, 0.6)
        self.assertEqual(stand_ev_from_distribution(12, (0, 0, 0, 0, 0, 1)).expected_value, 1.0)

    def test_non_natural_21_loses_to_dealer_natural_blackjack(self) -> None:
        rules = CoreRules()
        upcard = string_to_rank("10")
        counts = counts_from_cards(["A", "6"])

        result = ev_stand(21, upcard, counts, rules)
        oracle = oracle_stand_ev(21, upcard, counts, rules)

        self.assertAlmostEqual(dealer_natural_blackjack_probability(upcard, counts), 0.5)
        self.assertAlmostEqual(result.expected_value, oracle.expected_value)
        self.assertAlmostEqual(result.win_rate, 0.5)
        self.assertAlmostEqual(result.lose_rate, 0.5)
        self.assertAlmostEqual(result.push_rate, 0.0)

    def test_player_21_against_dealer_bust_prone_upcard_is_positive(self) -> None:
        state = build_core_state_from_inputs(["A", "5", "5"], "6", [], GameRules(number_of_decks=1))

        result = ev_stand(21, state.dealer_upcard_rank, state.deck_counts, state.rules)

        self.assertGreater(result.expected_value, 0.0)
        self.assertAlmostEqual(result.win_rate + result.lose_rate + result.push_rate, 1.0)


class ActionEvAccuracyTests(unittest.TestCase):
    def test_surrender_availability_and_ev(self) -> None:
        self.assertEqual(ev_surrender(CoreRules(surrender_allowed=True)).expected_value, -0.5)

        state = build_core_state_from_inputs(["10", "6"], "10", [], GameRules(surrender_allowed=False))
        ranking = calculate_action_evs_deterministic(state, ("hit", "stand", "double", "surrender"))
        self.assertNotIn("surrender", {action.action for action in ranking.actions})

        hit_hand_actions = get_legal_actions(Hand.from_values(["10", "2", "2"]), GameRules(surrender_allowed=True))
        blackjack_actions = get_legal_actions(Hand.from_values(["A", "10"]), GameRules(surrender_allowed=True))
        self.assertNotIn(Decision.SURRENDER, hit_hand_actions)
        self.assertEqual(blackjack_actions, (Decision.STAND,))

    def test_double_ev_draws_one_card_and_matches_independent_oracle(self) -> None:
        rules = CoreRules()
        upcard = string_to_rank("10")

        bust = ev_double(16, 0, upcard, counts_from_cards(["10"]), rules)
        self.assertEqual(bust.expected_value, -2.0)
        self.assertEqual(bust.lose_rate, 1.0)

        counts = counts_from_cards(["A", "2", "7", "8", "9", "10"])
        result = ev_double(11, 0, upcard, counts, rules)
        oracle = oracle_double_ev(11, 0, upcard, counts, rules)

        self.assertAlmostEqual(oracle_dealer_natural_blackjack_probability(upcard, counts), 1 / 6)
        self.assertAlmostEqual(result.expected_value, oracle.expected_value)
        self.assertAlmostEqual(result.win_rate, oracle.win_rate)
        self.assertAlmostEqual(result.lose_rate, oracle.lose_rate)
        self.assertAlmostEqual(result.push_rate, oracle.push_rate)
        self.assertGreaterEqual(result.expected_value, -2.0)
        self.assertLessEqual(result.expected_value, 2.0)

    def test_hit_ev_enumerates_remaining_cards_and_matches_independent_oracle(self) -> None:
        rules = CoreRules()
        upcard = string_to_rank("10")
        counts = counts_from_cards(["A", "2", "7", "8", "9", "10"])

        result = ev_hit(12, 0, upcard, counts, rules)
        oracle = oracle_hit_ev_cached(12, 0, upcard, counts, rules.dealer_hits_soft_17)

        self.assertAlmostEqual(result.expected_value, oracle.expected_value)
        self.assertAlmostEqual(result.win_rate, oracle.win_rate)
        self.assertAlmostEqual(result.lose_rate, oracle.lose_rate)
        self.assertAlmostEqual(result.push_rate, oracle.push_rate)
        self.assertGreaterEqual(result.expected_value, -1.0)
        self.assertLessEqual(result.expected_value, 1.0)

    def test_soft_hand_scenarios_return_finite_action_values(self) -> None:
        scenarios = (
            (["A", "6"], "10"),
            (["A", "7"], "10"),
            (["A", "9"], "10"),
            (["A", "9", "A"], "10"),
        )

        for player_hand, dealer_upcard in scenarios:
            with self.subTest(player_hand=player_hand, dealer_upcard=dealer_upcard):
                result = analyze_hand(
                    player_hand,
                    dealer_upcard,
                    [],
                    GameRules(surrender_allowed=True),
                    simulations=80,
                    seed=96,
                    engine_mode="deterministic",
                )

                for action in result["actions"]:
                    self.assertTrue(math.isfinite(action["ev"]))
                    self.assertTrue(math.isfinite(action["win_rate"]))
                    self.assertTrue(math.isfinite(action["lose_rate"]))
                    self.assertTrue(math.isfinite(action["push_rate"]))
                    self.assertTrue(math.isfinite(action["std_dev"]))

                if player_hand == ["A", "9", "A"]:
                    self.assertEqual(result["hand_analysis"]["total"], 21)
                    self.assertFalse(result["hand_analysis"]["is_blackjack"])


class BlackjackNaturalAccuracyTests(unittest.TestCase):
    def test_natural_blackjack_payout_and_push_probability(self) -> None:
        upcard = string_to_rank("10")
        counts = counts_from_cards(["A", "6"])

        result = natural_blackjack_stand_ev(upcard, counts, blackjack_payout_multiplier=1.5)
        self.assertAlmostEqual(result.expected_value, 0.75)
        self.assertAlmostEqual(result.win_rate, 0.5)
        self.assertAlmostEqual(result.push_rate, 0.5)

        action_result = ev_blackjack_stand(upcard, counts, CoreRules())
        self.assertAlmostEqual(action_result.expected_value, 0.75)
        self.assertAlmostEqual(action_result.push_rate, 0.5)

    def test_natural_blackjack_only_allows_stand_in_analysis(self) -> None:
        result = analyze_hand(
            ["A", "10"],
            "9",
            [],
            GameRules(surrender_allowed=True),
            simulations=100,
            seed=77,
            engine_mode="hybrid",
        )

        self.assertTrue(result["hand_analysis"]["is_blackjack"])
        self.assertEqual([action["action"] for action in result["actions"]], ["stand"])
        self.assertEqual(result["recommendation"]["best_action"], "stand")
        self.assertEqual(result["actions"][0]["ev"], 1.5)

    def test_natural_blackjack_respects_3_to_2_and_6_to_5_rules(self) -> None:
        three_to_two = analyze_hand(
            ["A", "10"],
            "9",
            [],
            GameRules(blackjack_payout="3:2"),
            simulations=80,
            seed=501,
            engine_mode="deterministic",
        )
        six_to_five = analyze_hand(
            ["A", "10"],
            "9",
            [],
            GameRules(blackjack_payout="6:5"),
            simulations=80,
            seed=501,
            engine_mode="deterministic",
        )

        self.assertAlmostEqual(three_to_two["actions"][0]["ev"], 1.5)
        self.assertAlmostEqual(six_to_five["actions"][0]["ev"], 1.2)

    def test_non_natural_21_does_not_receive_blackjack_payout(self) -> None:
        result = analyze_hand(
            ["7", "7", "7"],
            "9",
            [],
            GameRules(blackjack_payout="3:2"),
            simulations=80,
            seed=502,
            engine_mode="deterministic",
        )

        stand_ev = action_evs_by_name(result)["stand"]
        self.assertEqual(result["hand_analysis"]["total"], 21)
        self.assertFalse(result["hand_analysis"]["is_blackjack"])
        self.assertLessEqual(stand_ev, 1.0)
        self.assertNotEqual(stand_ev, 1.5)


class ShoeCompositionAndRankingAccuracyTests(unittest.TestCase):
    def test_seen_cards_remove_availability_and_shift_double_ev_coherently(self) -> None:
        low_cards_removed = ["2", "3", "4", "5", "6", "2", "3", "4", "5", "6"]
        high_cards_removed = ["10", "10", "10", "A", "A", "10", "A"]
        neutral_removed = ["2", "7", "10", "A", "5", "9"]

        rich_state = build_core_state_from_inputs(["5", "6"], "6", low_cards_removed, GameRules())
        poor_state = build_core_state_from_inputs(["5", "6"], "6", high_cards_removed, GameRules())
        neutral_state = build_core_state_from_inputs(["5", "6"], "6", neutral_removed, GameRules())

        base_counts = deck_counts_for_decks(6)
        self.assertEqual(rich_state.deck_counts[string_to_rank("2")], base_counts[string_to_rank("2")] - 2)
        self.assertEqual(poor_state.deck_counts[string_to_rank("10")], base_counts[string_to_rank("10")] - 4)
        self.assertEqual(neutral_state.cards_remaining, 52 * 6 - len(neutral_removed) - 3)

        rich = analyze_hand(["5", "6"], "6", low_cards_removed, GameRules(), 100, seed=90, engine_mode="hybrid")
        poor = analyze_hand(["5", "6"], "6", high_cards_removed, GameRules(), 100, seed=90, engine_mode="hybrid")
        neutral = analyze_hand(["5", "6"], "6", neutral_removed, GameRules(), 100, seed=90, engine_mode="hybrid")

        rich_double = action_evs_by_name(rich)["double"]
        poor_double = action_evs_by_name(poor)["double"]
        neutral_double = action_evs_by_name(neutral)["double"]

        self.assertGreater(rich_double, poor_double)
        self.assertNotEqual(rich_double, neutral_double)
        self.assertNotEqual(poor_double, neutral_double)

    def test_action_ranking_and_ev_sanity_across_engine_modes(self) -> None:
        scenarios = (
            (["10", "6"], "10"),
            (["A", "7"], "9"),
            (["5", "6"], "6"),
            (["8", "8"], "10"),
            (["A", "10"], "9"),
            (["10", "2"], "2"),
            (["10", "10"], "10"),
            (["4", "5"], "3"),
        )

        for player_hand, dealer_upcard in scenarios:
            for mode in ("deterministic", "hybrid", "monte_carlo", "legacy"):
                with self.subTest(player_hand=player_hand, dealer_upcard=dealer_upcard, mode=mode):
                    result = analyze_hand(
                        player_hand,
                        dealer_upcard,
                        [],
                        GameRules(),
                        simulations=200,
                        seed=1234,
                        engine_mode=mode,
                    )
                    actions = result["actions"]
                    self.assertGreater(len(actions), 0)
                    self.assertEqual(result["recommendation"]["best_action"], actions[0]["action"])
                    self.assertEqual(
                        [action["ev"] for action in actions],
                        sorted((action["ev"] for action in actions), reverse=True),
                    )
                    for action in actions:
                        self.assertTrue(math.isfinite(action["ev"]))
                        self.assertTrue(math.isfinite(action["win_rate"]))
                        self.assertTrue(math.isfinite(action["lose_rate"]))
                        self.assertTrue(math.isfinite(action["push_rate"]))
                        self.assertGreaterEqual(action["win_rate"], 0.0)
                        self.assertLessEqual(action["win_rate"], 1.0)
                        self.assertGreaterEqual(action["lose_rate"], 0.0)
                        self.assertLessEqual(action["lose_rate"], 1.0)
                        self.assertGreaterEqual(action["push_rate"], 0.0)
                        self.assertLessEqual(action["push_rate"], 1.0)
                        if action["action"] == "double":
                            self.assertGreaterEqual(action["ev"], -2.0)
                            self.assertLessEqual(action["ev"], 2.0)
                        elif action["action"] == "surrender":
                            self.assertEqual(action["ev"], -0.5)
                        else:
                            self.assertGreaterEqual(action["ev"], -1.0)
                            self.assertLessEqual(action["ev"], 1.5)

    def test_deterministic_and_hybrid_match_for_supported_actions(self) -> None:
        deterministic = analyze_hand(
            ["10", "6"],
            "10",
            [],
            GameRules(),
            simulations=100,
            seed=222,
            engine_mode="deterministic",
        )
        hybrid = analyze_hand(
            ["10", "6"],
            "10",
            [],
            GameRules(),
            simulations=100,
            seed=333,
            engine_mode="hybrid",
        )

        self.assertEqual(deterministic["metadata"]["simulations_used"], 0)
        self.assertEqual(hybrid["metadata"]["simulations_used"], 0)
        self.assertEqual(action_evs_by_name(deterministic), action_evs_by_name(hybrid))

        split_deterministic = analyze_hand(
            ["8", "8"],
            "10",
            [],
            GameRules(),
            simulations=100,
            seed=444,
            engine_mode="deterministic",
        )
        split_hybrid = analyze_hand(
            ["8", "8"],
            "10",
            [],
            GameRules(),
            simulations=100,
            seed=444,
            engine_mode="hybrid",
        )
        self.assertIn("split", split_deterministic["metadata"]["unsupported_actions"])
        self.assertIn("split", split_hybrid["metadata"]["monte_carlo_fallback_actions"])


if __name__ == "__main__":
    unittest.main()
