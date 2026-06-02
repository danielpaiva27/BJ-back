import unittest

from blackjack_risk_engine.risk import suggest_bet


class BettingSuggestionTests(unittest.TestCase):
    def test_low_true_count_suggests_minimum_bet(self) -> None:
        suggestion = suggest_bet(
            true_count=0,
            minimum_bet=10,
            bankroll=1000,
            risk_profile="moderate",
        )

        self.assertEqual(suggestion.suggested_bet, 10)
        self.assertEqual(suggestion.bet_units, 1)

    def test_high_true_count_increases_bet(self) -> None:
        low = suggest_bet(true_count=0, minimum_bet=10, bankroll=1000, risk_profile="moderate")
        high = suggest_bet(true_count=5, minimum_bet=10, bankroll=1000, risk_profile="moderate")

        self.assertGreater(high.suggested_bet, low.suggested_bet)
        self.assertEqual(high.bet_units, 3)

    def test_suggestion_does_not_exceed_bankroll_limit(self) -> None:
        suggestion = suggest_bet(
            true_count=6,
            minimum_bet=10,
            bankroll=200,
            risk_profile="aggressive",
        )

        self.assertEqual(suggestion.suggested_bet, 10)
        self.assertEqual(suggestion.bet_units, 1)

    def test_profiles_generate_different_suggestions(self) -> None:
        conservative = suggest_bet(true_count=5, minimum_bet=10, bankroll=10_000, risk_profile="conservative")
        moderate = suggest_bet(true_count=5, minimum_bet=10, bankroll=10_000, risk_profile="moderate")
        aggressive = suggest_bet(true_count=5, minimum_bet=10, bankroll=10_000, risk_profile="aggressive")

        self.assertLess(conservative.suggested_bet, moderate.suggested_bet)
        self.assertLess(moderate.suggested_bet, aggressive.suggested_bet)

    def test_invalid_profile_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "risk_profile must be one of"):
            suggest_bet(true_count=2, minimum_bet=10, bankroll=1000, risk_profile="reckless")


if __name__ == "__main__":
    unittest.main()
