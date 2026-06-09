import json
import math
import unittest

from fastapi.testclient import TestClient

from app.main import app


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def _valid_payload(self) -> dict:
        return {
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
            },
            "simulations": 100,
            "seed": 42,
            "bankroll": 1000,
            "minimum_bet": 10,
            "risk_profile": "moderate",
        }

    def _seen_cards_with_high_dealer_natural_pressure(self) -> list[str]:
        return [
            *(["2"] * 4),
            *(["3"] * 4),
            *(["4"] * 4),
            *(["5"] * 3),
            *(["6"] * 3),
            *(["7"] * 4),
            *(["8"] * 4),
            *(["9"] * 4),
            *(["10"] * 14),
        ]

    def test_health_returns_200(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "blackjack-risk-engine")
        self.assertIn("version", payload)

    def test_analyze_hand_valid_payload_returns_200(self) -> None:
        response = self.client.post("/analyze-hand", json=self._valid_payload())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            set(payload),
            {"input", "rules", "hand_analysis", "counting", "actions", "recommendation", "betting", "metadata"},
        )

    def test_analyze_hand_accepts_optional_monte_carlo_config(self) -> None:
        payload = self._valid_payload()
        payload.update(
            {
                "player_hand": ["8", "8"],
                "seen_cards": [],
                "simulations": 50,
                "monte_carlo_parallel_enabled": False,
                "simulation_chunk_size": 10,
                "max_workers": 2,
            }
        )

        response = self.client.post("/analyze-hand", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn("split", {action["action"] for action in response.json()["actions"]})

    def test_analyze_hand_returns_recommendation(self) -> None:
        response = self.client.post("/analyze-hand", json=self._valid_payload())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("best_action", payload["recommendation"])
        self.assertIn(payload["recommendation"]["best_action"], {"hit", "stand", "double", "split", "surrender"})

    def test_analyze_hand_returns_actions(self) -> None:
        response = self.client.post("/analyze-hand", json=self._valid_payload())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsInstance(payload["actions"], list)
        self.assertGreater(len(payload["actions"]), 0)
        self.assertIn("action", payload["actions"][0])
        self.assertIn("ev", payload["actions"][0])

    def test_analyze_hand_invalid_card_returns_422(self) -> None:
        invalid_payload = self._valid_payload()
        invalid_payload["dealer_upcard"] = "K"

        response = self.client.post("/analyze-hand", json=invalid_payload)

        self.assertEqual(response.status_code, 422)

    def test_analyze_hand_invalid_simulations_returns_422(self) -> None:
        invalid_payload = self._valid_payload()
        invalid_payload["simulations"] = 0

        response = self.client.post("/analyze-hand", json=invalid_payload)

        self.assertEqual(response.status_code, 422)

    def test_analyze_hand_invalid_engine_mode_returns_422(self) -> None:
        invalid_payload = self._valid_payload()
        invalid_payload["engine_mode"] = "banana"

        response = self.client.post("/analyze-hand", json=invalid_payload)

        self.assertEqual(response.status_code, 422)
        self.assertIn("engine_mode", response.text)

    def test_analyze_hand_double_vs_dealer_natural_keeps_values_finite(self) -> None:
        payload = self._valid_payload()
        payload.update(
            {
                "player_hand": ["5", "6"],
                "dealer_upcard": "10",
                "seen_cards": self._seen_cards_with_high_dealer_natural_pressure(),
                "engine_mode": "deterministic",
                "simulations": 80,
                "seed": 99,
            }
        )
        payload["rules"]["number_of_decks"] = 1

        response = self.client.post("/analyze-hand", json=payload)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        actions = {action["action"]: action for action in data["actions"]}

        self.assertIn("double", actions)
        self.assertEqual(data["metadata"]["analysis_method"], "deterministic_dp")
        self.assertGreater(actions["double"]["ev"], -2.0)

        serialized = json.dumps(data).lower()
        self.assertNotIn("nan", serialized)
        self.assertNotIn("infinity", serialized)

        for field in ("ev", "win_rate", "lose_rate", "push_rate", "std_dev"):
            self.assertTrue(math.isfinite(actions["double"][field]))

    def test_analyze_hand_response_keeps_numeric_outputs_finite(self) -> None:
        response = self.client.post("/analyze-hand", json=self._valid_payload())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        serialized = json.dumps(payload).lower()
        self.assertNotIn("nan", serialized)
        self.assertNotIn("infinity", serialized)

        self.assertTrue(math.isfinite(payload["counting"]["true_count"]))
        self.assertGreaterEqual(payload["counting"]["cards_remaining"], 0)

        for action in payload["actions"]:
            for field in (
                "ev",
                "win_rate",
                "lose_rate",
                "push_rate",
                "std_dev",
                "standard_error",
            ):
                self.assertTrue(math.isfinite(action[field]), f"{field} should be finite")

            low, high = action["confidence_interval_95"]
            self.assertTrue(math.isfinite(low))
            self.assertTrue(math.isfinite(high))


if __name__ == "__main__":
    unittest.main()
