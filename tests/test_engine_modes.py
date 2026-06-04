import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from blackjack_risk_engine.ev import analyze_action, analyze_hand
from blackjack_risk_engine.rules import GameRules


class EngineModeTests(unittest.TestCase):
    def test_default_engine_mode_is_hybrid(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = analyze_hand(["10", "6"], "10", [], GameRules(), simulations=50, seed=10)

        self.assertEqual(result["metadata"]["engine_mode"], "hybrid")
        self.assertEqual(result["metadata"]["analysis_method"], "deterministic_dp")
        self.assertEqual(result["metadata"]["simulations_used"], 0)

    def test_environment_engine_mode_is_used_when_request_omits_mode(self) -> None:
        with patch.dict(os.environ, {"ENGINE_MODE": "deterministic"}, clear=True):
            result = analyze_hand(["8", "8"], "10", [], GameRules(), simulations=50, seed=11)

        self.assertEqual(result["metadata"]["engine_mode"], "deterministic")
        self.assertEqual(result["metadata"]["analysis_method"], "deterministic_dp_unsupported_actions_ignored")
        self.assertIn("split", result["metadata"]["unsupported_actions"])
        self.assertNotIn("split", {action["action"] for action in result["actions"]})

    def test_request_engine_mode_overrides_environment(self) -> None:
        with patch.dict(os.environ, {"ENGINE_MODE": "deterministic"}, clear=True):
            result = analyze_hand(
                ["8", "8"],
                "10",
                [],
                GameRules(),
                simulations=50,
                seed=12,
                engine_mode="hybrid",
            )

        self.assertEqual(result["metadata"]["engine_mode"], "hybrid")
        self.assertIn("split", {action["action"] for action in result["actions"]})
        self.assertEqual(result["metadata"]["monte_carlo_fallback_actions"], ["split"])

    def test_monte_carlo_mode_simulates_all_legal_actions(self) -> None:
        result = analyze_hand(
            ["10", "6"],
            "10",
            [],
            GameRules(),
            simulations=20,
            seed=13,
            engine_mode="monte_carlo",
        )

        self.assertEqual(result["metadata"]["engine_mode"], "monte_carlo")
        self.assertEqual(result["metadata"]["analysis_method"], "optimized_monte_carlo")
        self.assertEqual(result["metadata"]["simulations_used"], 60)
        self.assertEqual(set(result["metadata"]["monte_carlo_fallback_actions"]), {"hit", "stand", "double"})

    def test_legacy_mode_uses_legacy_monte_carlo(self) -> None:
        result = analyze_hand(
            ["10", "6"],
            "10",
            [],
            GameRules(),
            simulations=20,
            seed=14,
            engine_mode="legacy",
        )

        self.assertEqual(result["metadata"]["engine_mode"], "legacy")
        self.assertEqual(result["metadata"]["analysis_method"], "legacy_monte_carlo")
        self.assertEqual(result["metadata"]["simulations_used"], 60)

    def test_analyze_action_rejects_unsupported_deterministic_action(self) -> None:
        with self.assertRaisesRegex(ValueError, "not supported by deterministic engine mode"):
            analyze_action(
                ["8", "8"],
                "10",
                [],
                GameRules(),
                "split",
                simulations=20,
                seed=15,
                engine_mode="deterministic",
            )


class EngineModeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_endpoint_accepts_optional_engine_mode(self) -> None:
        response = self.client.post(
            "/analyze-hand",
            json={
                "player_hand": ["8", "8"],
                "dealer_upcard": "10",
                "seen_cards": [],
                "engine_mode": "deterministic",
                "simulations": 30,
                "seed": 16,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["metadata"]["engine_mode"], "deterministic")
        self.assertNotIn("split", {action["action"] for action in payload["actions"]})


if __name__ == "__main__":
    unittest.main()
