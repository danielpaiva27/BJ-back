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


if __name__ == "__main__":
    unittest.main()
