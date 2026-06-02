import io
import json
import unittest
from contextlib import redirect_stdout

import main


class CliTests(unittest.TestCase):
    def test_parse_card_list_accepts_comma_separated_values(self) -> None:
        self.assertEqual(main.parse_card_list("10,6,A"), ["10", "6", "A"])

    def test_parse_card_list_accepts_empty_seen_cards(self) -> None:
        self.assertEqual(main.parse_card_list(""), [])

    def test_main_prints_cli_analysis(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main.main(
                [
                    "--player",
                    "10,6",
                    "--dealer",
                    "10",
                    "--seen",
                    "2,5",
                    "--decks",
                    "1",
                    "--simulations",
                    "3",
                    "--seed",
                    "123",
                    "--minimum-bet",
                    "10",
                    "--bankroll",
                    "1000",
                    "--risk-profile",
                    "moderate",
                ]
            )

        text = output.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Player hand", text)
        self.assertIn("Hi-Lo count", text)
        self.assertIn("- running_count: 1", text)
        self.assertIn("- cards_remaining: 47", text)
        self.assertIn("- deck_status: favorável", text)
        self.assertIn("Bet suggestion", text)
        self.assertIn("- suggested_bet:", text)
        self.assertIn("- risk_profile: moderate", text)
        self.assertIn("modelo academico/simulacional", text.lower())
        self.assertIn("- hit:", text)
        self.assertIn("- stand:", text)
        self.assertIn("std_dev=", text)
        self.assertIn("standard_error=", text)
        self.assertIn("confidence_interval_95=[", text)
        self.assertIn("Strategy comparison", text)
        self.assertIn("- monte_carlo_action:", text)
        self.assertIn("- basic_strategy_action:", text)
        self.assertIn("- agreement:", text)
        self.assertIn("Recommended action:", text)

    def test_main_can_print_json_analysis(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main.main(
                [
                    "--player",
                    "10,6",
                    "--dealer",
                    "10",
                    "--seen",
                    "2,5",
                    "--decks",
                    "1",
                    "--simulations",
                    "3",
                    "--seed",
                    "123",
                    "--json",
                ]
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            set(payload),
            {"input", "rules", "hand_analysis", "counting", "actions", "recommendation", "betting", "metadata"},
        )
        self.assertEqual(payload["input"]["player"], ["10", "6"])
        self.assertEqual(payload["metadata"]["simulation_seed"], 123)
        self.assertEqual(payload["metadata"]["simulations"], 3)
        self.assertIsInstance(payload["actions"], list)
        self.assertIn("best_action", payload["recommendation"])


if __name__ == "__main__":
    unittest.main()
