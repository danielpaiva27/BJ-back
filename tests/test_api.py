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

    def _valid_pre_round_payload(self) -> dict:
        return {
            "number_of_decks": 6,
            "seen_cards": ["2", "3", "4", "5", "6", "10", "10", "A", "9", "8"],
            "bankroll": 1000,
            "minimum_bet": 10,
            "rules": {
                "dealer_hits_soft_17": False,
                "blackjack_payout": "3:2",
                "double_allowed": True,
                "double_after_split": True,
                "surrender_allowed": False,
                "max_splits": 3,
                "dealer_peek": True,
            },
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

    def test_pre_round_then_analyze_hand_contract_flow_returns_finite_and_compatible_payloads(self) -> None:
        pre_round_payload = self._valid_pre_round_payload()
        pre_round_response = self.client.post("/pre-round-analysis", json=pre_round_payload)

        self.assertEqual(pre_round_response.status_code, 200)
        pre_round_data = pre_round_response.json()
        self.assertIn("systems", pre_round_data)
        self.assertEqual(len(pre_round_data["systems"]), 3)

        system_ids = [system["system_id"] for system in pre_round_data["systems"]]
        self.assertEqual(system_ids, ["hi_lo", "hi_opt_ii", "wong_halves"])
        self.assertEqual(len(set(system_ids)), len(system_ids))

        required_system_fields = (
            "system_id",
            "label",
            "running_count",
            "true_count",
            "betting_true_count",
            "estimated_player_edge",
            "suggested_units",
            "suggested_amount",
            "recommendation_status",
            "recommendation_text",
            "estimated_risk_of_ruin",
            "risk_of_ruin_limit",
        )
        for system in pre_round_data["systems"]:
            for field in required_system_fields:
                self.assertIn(field, system)
                self.assertIsNotNone(system[field])

            for numeric_field in (
                "true_count",
                "betting_true_count",
                "estimated_player_edge",
                "suggested_amount",
                "estimated_risk_of_ruin",
                "risk_of_ruin_limit",
            ):
                self.assertTrue(
                    math.isfinite(system[numeric_field]),
                    f"{numeric_field} should be finite for {system['system_id']}",
                )

        hi_opt_ii = next(system for system in pre_round_data["systems"] if system["system_id"] == "hi_opt_ii")
        self.assertIn("ace_side_count", hi_opt_ii)
        self.assertIn("betting_running_count", hi_opt_ii)
        self.assertIsInstance(hi_opt_ii["ace_side_count"], dict)

        wong_halves = next(system for system in pre_round_data["systems"] if system["system_id"] == "wong_halves")
        self.assertIn("scaled_running_count", wong_halves)
        self.assertIn("scale", wong_halves)

        pre_round_serialized = json.dumps(pre_round_data).lower()
        self.assertNotIn("nan", pre_round_serialized)
        self.assertNotIn("infinity", pre_round_serialized)

        analyze_payload = self._valid_payload()
        analyze_payload["seen_cards"] = pre_round_payload["seen_cards"]
        analyze_payload["rules"] = {
            **analyze_payload["rules"],
            **pre_round_payload["rules"],
            "number_of_decks": pre_round_payload["number_of_decks"],
        }

        analyze_response = self.client.post("/analyze-hand", json=analyze_payload)

        self.assertEqual(analyze_response.status_code, 200)
        analyze_data = analyze_response.json()
        self.assertIn("recommendation", analyze_data)
        self.assertIn("best_action", analyze_data["recommendation"])
        self.assertIn(analyze_data["recommendation"]["best_action"], {"hit", "stand", "double", "split", "surrender"})

        self.assertIn("metadata", analyze_data)
        self.assertIn("engine_mode", analyze_data["metadata"])
        self.assertIsInstance(analyze_data["metadata"]["engine_mode"], str)

        for action in analyze_data["actions"]:
            for numeric_field in ("ev", "win_rate", "lose_rate", "push_rate", "std_dev", "standard_error"):
                self.assertTrue(
                    math.isfinite(action[numeric_field]),
                    f"{numeric_field} should be finite for action {action['action']}",
                )

        analyze_serialized = json.dumps(analyze_data).lower()
        self.assertNotIn("nan", analyze_serialized)
        self.assertNotIn("infinity", analyze_serialized)

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
