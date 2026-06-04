import json
import unittest

from blackjack_risk_engine.decisions import Decision
from blackjack_risk_engine.ev import ActionAnalysis, analyze_action, analyze_hand
from blackjack_risk_engine.rules import GameRules


class ExpectedValueMonteCarloTests(unittest.TestCase):
    def test_analyze_action_returns_expected_shape(self) -> None:
        result = analyze_action(
            player_hand=["10", "6"],
            dealer_up_card="10",
            seen_cards=[],
            rules=GameRules(),
            action="stand",
            simulations=10,
            seed=123,
        )

        self.assertIsInstance(result, ActionAnalysis)
        self.assertEqual(result.action, Decision.STAND)
        self.assertEqual(result.simulations, 10)
        self.assertEqual(result.wins + result.losses + result.pushes, 10)
        self.assertAlmostEqual(result.win_rate + result.lose_rate + result.push_rate, 1.0)
        self.assertGreaterEqual(result.std_dev, 0)
        self.assertGreaterEqual(result.standard_error, 0)
        self.assertEqual(len(result.confidence_interval_95), 2)

    def test_natural_blackjack_has_payout_in_expected_value(self) -> None:
        result = analyze_action(
            player_hand=["A", "10"],
            dealer_up_card="9",
            seen_cards=[],
            rules=GameRules(blackjack_payout="3:2"),
            action="stand",
            simulations=5,
            seed=99,
        )

        self.assertEqual(result.expected_value, 1.5)
        self.assertEqual(result.wins, 5)
        self.assertEqual(result.losses, 0)
        self.assertEqual(result.pushes, 0)
        self.assertEqual(result.std_dev, 0)
        self.assertEqual(result.standard_error, 0)
        self.assertEqual(result.confidence_interval_95, (1.5, 1.5))

    def test_seed_makes_analyze_action_reproducible(self) -> None:
        first = analyze_action(["10", "6"], "10", [], GameRules(), "hit", 20, seed=42)
        second = analyze_action(["10", "6"], "10", [], GameRules(), "hit", 20, seed=42)

        self.assertEqual(first, second)

    def test_stand_action_uses_deterministic_dealer_distribution(self) -> None:
        result = analyze_action(["10", "6"], "10", [], GameRules(), "stand", 100, seed=123)

        self.assertEqual(result.action, Decision.STAND)
        self.assertEqual(result.standard_error, 0)
        self.assertEqual(result.confidence_interval_95, (result.expected_value, result.expected_value))
        self.assertEqual(result.wins + result.losses + result.pushes, 100)

    def test_deterministic_actions_are_seed_independent(self) -> None:
        first = analyze_hand(["10", "6"], "10", [], GameRules(), simulations=100, seed=1)
        second = analyze_hand(["10", "6"], "10", [], GameRules(), simulations=100, seed=999)

        self.assertEqual(first["actions"], second["actions"])
        self.assertEqual(first["recommendation"], second["recommendation"])
        self.assertEqual(first["metadata"]["analysis_method"], "deterministic_dp")

    def test_analyze_hand_returns_json_serializable_contract(self) -> None:
        result = analyze_hand(
            player_hand=["10", "6"],
            dealer_up_card="10",
            seen_cards=["2"],
            rules=GameRules(),
            simulations=3,
            seed=7,
        )

        self.assertEqual(
            set(result),
            {"input", "rules", "hand_analysis", "counting", "actions", "recommendation", "betting", "metadata"},
        )
        json.dumps(result)
        self.assertEqual(result["input"]["player"], ["10", "6"])
        self.assertEqual(result["metadata"]["simulation_seed"], 7)
        self.assertEqual(result["metadata"]["simulations"], 3)
        self.assertIn("execution_time_ms", result["metadata"])

    def test_analyze_hand_actions_are_sorted_by_ev(self) -> None:
        result = analyze_hand(["10", "6"], "10", [], GameRules(), simulations=10, seed=7)

        self.assertEqual({action["action"] for action in result["actions"]}, {"hit", "stand", "double"})
        self.assertGreaterEqual(result["actions"][0]["ev"], result["actions"][1]["ev"])
        self.assertGreaterEqual(result["actions"][1]["ev"], result["actions"][2]["ev"])

    def test_analyze_hand_includes_count_metadata(self) -> None:
        result = analyze_hand(
            player_hand=["10", "6"],
            dealer_up_card="10",
            seen_cards=["2", "5"],
            rules=GameRules(number_of_decks=1),
            simulations=5,
            seed=7,
        )

        self.assertEqual(result["counting"]["running_count"], 1)
        self.assertEqual(result["counting"]["cards_remaining"], 47)
        self.assertAlmostEqual(result["counting"]["true_count"], 1 / (47 / 52))
        self.assertEqual(result["counting"]["deck_status"], "favorável")

    def test_analyze_hand_includes_recommendation(self) -> None:
        result = analyze_hand(["10", "6"], "10", [], GameRules(), simulations=5, seed=7)

        self.assertIn(result["recommendation"]["monte_carlo_action"], {"hit", "stand", "double"})
        self.assertEqual(result["recommendation"]["basic_strategy_action"], "hit")
        self.assertIsInstance(result["recommendation"]["strategy_agreement"], bool)
        self.assertIn("confidence", result["recommendation"])
        self.assertIn("explanation", result["recommendation"])

    def test_analyze_hand_includes_betting(self) -> None:
        result = analyze_hand(
            ["10", "6"],
            "10",
            ["2", "5"],
            GameRules(number_of_decks=1),
            simulations=5,
            seed=7,
            minimum_bet=10,
            bankroll=1000,
            risk_profile="moderate",
        )

        self.assertEqual(set(result["betting"]), {"suggested_bet", "bet_units", "risk_profile", "explanation"})
        self.assertEqual(result["betting"]["risk_profile"], "moderate")

    def test_analyze_hand_omits_double_when_not_allowed(self) -> None:
        result = analyze_hand(["10", "6"], "10", [], GameRules(double_allowed=False), simulations=10, seed=7)

        self.assertEqual({action["action"] for action in result["actions"]}, {"hit", "stand"})

    def test_analyze_hand_omits_double_for_more_than_two_card_hand(self) -> None:
        result = analyze_hand(["10", "2", "3"], "10", [], GameRules(), simulations=10, seed=7)

        self.assertEqual({action["action"] for action in result["actions"]}, {"hit", "stand"})

    def test_analyze_hand_includes_split_when_legal(self) -> None:
        result = analyze_hand(["8", "8"], "10", [], GameRules(), simulations=5, seed=7)

        self.assertEqual({action["action"] for action in result["actions"]}, {"hit", "stand", "double", "split"})

    def test_analyze_hand_omits_split_when_limit_reached(self) -> None:
        result = analyze_hand(["8", "8"], "10", [], GameRules(max_splits=0), simulations=5, seed=7)

        self.assertNotIn("split", {action["action"] for action in result["actions"]})

    def test_analyze_hand_includes_surrender_when_allowed(self) -> None:
        result = analyze_hand(["10", "6"], "10", [], GameRules(surrender_allowed=True), simulations=5, seed=7)

        self.assertIn("surrender", {action["action"] for action in result["actions"]})

    def test_analyze_hand_omits_surrender_when_not_allowed(self) -> None:
        result = analyze_hand(["10", "6"], "10", [], GameRules(surrender_allowed=False), simulations=5, seed=7)

        self.assertNotIn("surrender", {action["action"] for action in result["actions"]})

    def test_natural_blackjack_analysis_only_exposes_stand(self) -> None:
        result = analyze_hand(["A", "10"], "9", [], GameRules(surrender_allowed=True), simulations=5, seed=7)

        self.assertEqual([action["action"] for action in result["actions"]], ["stand"])
        self.assertEqual(result["actions"][0]["ev"], 1.5)

    def test_analyze_action_surrender_is_minus_half(self) -> None:
        result = analyze_action(["10", "6"], "10", [], GameRules(surrender_allowed=True), "surrender", 5, seed=7)

        self.assertEqual(result.expected_value, -0.5)
        self.assertEqual(result.losses, 5)
        self.assertEqual(result.std_dev, 0)

    def test_analyze_action_rejects_illegal_double(self) -> None:
        with self.assertRaisesRegex(ValueError, "action double is not legal"):
            analyze_action(["10", "6"], "10", [], GameRules(double_allowed=False), "double", 1)

    def test_analyze_action_rejects_illegal_split(self) -> None:
        with self.assertRaisesRegex(ValueError, "action split is not legal"):
            analyze_action(["8", "9"], "10", [], GameRules(), "split", 1)

    def test_invalid_simulation_count_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "simulations must be greater than zero"):
            analyze_action(["10", "6"], "10", [], GameRules(), "stand", 0)

    def test_invalid_action_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "action must be one of: hit, stand, double, split, surrender"):
            analyze_action(["10", "6"], "10", [], GameRules(), "insurance", 1)


if __name__ == "__main__":
    unittest.main()
