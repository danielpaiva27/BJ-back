import copy
import unittest

from fastapi.testclient import TestClient

from app.main import app
from blackjack_risk_engine.ev import analyze_hand
from blackjack_risk_engine.rules import GameRules


class EngineRegressionBaselineTests(unittest.TestCase):
    def test_fixed_seed_scenarios_preserve_current_recommendations_and_evs(self) -> None:
        cases = [
            {
                "name": "hard_16_vs_10",
                "player_hand": ["10", "6"],
                "dealer_up_card": "10",
                "seen_cards": ["2", "5", "6", "A", "10"],
                "seed": 101,
                "best_action": "hit",
                "actions": [
                    ("hit", -0.5675916930509228, 5, 23, 2),
                    ("stand", -0.5784065991336804, 6, 24, 0),
                    ("double", -1.1351833861018457, 5, 23, 2),
                ],
            },
            {
                "name": "soft_18_vs_9",
                "player_hand": ["A", "7"],
                "dealer_up_card": "9",
                "seen_cards": [],
                "seed": 102,
                "best_action": "hit",
                "actions": [
                    ("hit", -0.09846902159307445, 12, 15, 3),
                    ("stand", -0.18263993715641147, 10, 16, 4),
                    ("double", -0.2848249295012202, 11, 16, 3),
                ],
            },
            {
                "name": "hard_11_vs_6",
                "player_hand": ["5", "6"],
                "dealer_up_card": "6",
                "seen_cards": [],
                "seed": 103,
                "best_action": "double",
                "actions": [
                    ("double", 0.6826646957912995, 19, 9, 2),
                    ("hit", 0.34133234789564976, 19, 9, 2),
                    ("stand", -0.15082601322232542, 13, 17, 0),
                ],
            },
            {
                "name": "pair_8s_vs_10",
                "player_hand": ["8", "8"],
                "dealer_up_card": "10",
                "seen_cards": [],
                "seed": 104,
                "best_action": "split",
                "actions": [
                    ("split", -0.4666666666666667, 9, 17, 4),
                    ("hit", -0.5653973011785047, 6, 22, 2),
                    ("stand", -0.5728258585202568, 6, 24, 0),
                    ("double", -1.1307946023570095, 6, 22, 2),
                ],
            },
            {
                "name": "natural_blackjack_vs_9",
                "player_hand": ["A", "10"],
                "dealer_up_card": "9",
                "seen_cards": [],
                "seed": 105,
                "best_action": "stand",
                "actions": [("stand", 1.5, 30, 0, 0)],
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                result = analyze_hand(
                    player_hand=case["player_hand"],
                    dealer_up_card=case["dealer_up_card"],
                    seen_cards=case["seen_cards"],
                    rules=GameRules(),
                    simulations=30,
                    seed=case["seed"],
                )

                self.assertEqual(result["recommendation"]["best_action"], case["best_action"])
                self.assertEqual([action["action"] for action in result["actions"]], [item[0] for item in case["actions"]])
                for action, expected in zip(result["actions"], case["actions"]):
                    _name, ev, wins, losses, pushes = expected
                    self.assertAlmostEqual(action["ev"], ev)
                    self.assertEqual(action["wins"], wins)
                    self.assertEqual(action["losses"], losses)
                    self.assertEqual(action["pushes"], pushes)

    def test_analyze_hand_seed_is_reproducible_except_execution_time(self) -> None:
        first = analyze_hand(["10", "6"], "10", ["2", "5"], GameRules(), simulations=50, seed=777)
        second = analyze_hand(["10", "6"], "10", ["2", "5"], GameRules(), simulations=50, seed=777)

        first_without_timing = copy.deepcopy(first)
        second_without_timing = copy.deepcopy(second)
        for key in ("execution_time_ms", "elapsed_ms", "cache_hits", "cache_misses"):
            first_without_timing["metadata"].pop(key)
            second_without_timing["metadata"].pop(key)

        self.assertEqual(first_without_timing, second_without_timing)


class AnalyzeHandEndpointRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_endpoint_accepts_current_frontend_contract_payload(self) -> None:
        payload = {
            "player_hand": ["10", "6"],
            "dealer_upcard": "10",
            "seen_cards": ["2", "5", "6", "A", "10"],
            "rules": {
                "number_of_decks": 6,
                "dealer_hits_soft_17": False,
                "blackjack_payout": "3:2",
                "double_allowed": True,
                "double_after_split": True,
                "surrender_allowed": False,
                "max_splits": 3,
                "dealer_peek": True,
                "hit_split_aces": False,
                "resplit_aces": False,
            },
            "simulations": 30,
            "seed": 42,
            "bankroll": 1000,
            "minimum_bet": 10,
            "risk_profile": "moderate",
        }

        response = self.client.post("/analyze-hand", json=payload)

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(
            set(result),
            {"input", "rules", "hand_analysis", "counting", "actions", "recommendation", "betting", "metadata"},
        )
        self.assertEqual(result["metadata"]["simulation_seed"], 42)
        self.assertEqual(result["metadata"]["simulations"], 30)
        self.assertEqual(result["input"]["player"], ["10", "6"])
        self.assertEqual(result["input"]["dealer"], "10")

    def test_endpoint_response_contains_ranked_actions(self) -> None:
        response = self.client.post(
            "/analyze-hand",
            json={
                "player_hand": ["8", "8"],
                "dealer_upcard": "10",
                "seen_cards": [],
                "simulations": 30,
                "seed": 104,
            },
        )

        self.assertEqual(response.status_code, 200)
        actions = response.json()["actions"]
        self.assertEqual([action["action"] for action in actions], ["split", "hit", "stand", "double"])
        self.assertEqual([action["ev"] for action in actions], sorted((action["ev"] for action in actions), reverse=True))
        for action in actions:
            self.assertEqual(
                set(action),
                {
                    "action",
                    "ev",
                    "win_rate",
                    "lose_rate",
                    "push_rate",
                    "simulations",
                    "wins",
                    "losses",
                    "pushes",
                    "std_dev",
                    "standard_error",
                    "confidence_interval_95",
                },
            )


if __name__ == "__main__":
    unittest.main()
