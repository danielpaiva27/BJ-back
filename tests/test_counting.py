import unittest

from blackjack_risk_engine.cards import Card, Rank
from blackjack_risk_engine.counting import analyze_count, deck_status, hi_lo_value, running_count, true_count
from blackjack_risk_engine.rules import GameRules


class CountingTests(unittest.TestCase):
    def test_hi_lo_values(self) -> None:
        self.assertEqual(hi_lo_value(Card(Rank.TWO)), 1)
        self.assertEqual(hi_lo_value(Card(Rank.THREE)), 1)
        self.assertEqual(hi_lo_value(Card(Rank.FOUR)), 1)
        self.assertEqual(hi_lo_value(Card(Rank.FIVE)), 1)
        self.assertEqual(hi_lo_value(Card(Rank.SIX)), 1)
        self.assertEqual(hi_lo_value(Card(Rank.SEVEN)), 0)
        self.assertEqual(hi_lo_value(Card(Rank.EIGHT)), 0)
        self.assertEqual(hi_lo_value(Card(Rank.NINE)), 0)
        self.assertEqual(hi_lo_value(Card(Rank.TEN)), -1)
        self.assertEqual(hi_lo_value(Card(Rank.ACE)), -1)

    def test_running_and_true_count(self) -> None:
        cards = [
            Card(Rank.TWO),
            Card(Rank.FIVE),
            Card(Rank.TEN),
        ]

        self.assertEqual(running_count(cards), 1)
        self.assertEqual(true_count(4, cards_remaining=104), 2)
        self.assertEqual(true_count(4, decks_remaining=2), 2)

    def test_true_count_handles_zero_remaining_cards_safely(self) -> None:
        self.assertEqual(true_count(4, cards_remaining=0), 0)

    def test_deck_status_classification(self) -> None:
        self.assertEqual(deck_status(-3), "muito desfavorável")
        self.assertEqual(deck_status(-2), "desfavorável")
        self.assertEqual(deck_status(0), "neutro")
        self.assertEqual(deck_status(2), "favorável")
        self.assertEqual(deck_status(3), "muito favorável")

    def test_analyze_count_returns_count_report(self) -> None:
        report = analyze_count(["2", "5", "10"], GameRules(number_of_decks=1))

        self.assertEqual(report.running_count, 1)
        self.assertEqual(report.cards_remaining, 49)
        self.assertAlmostEqual(report.true_count, 1 / (49 / 52))
        self.assertEqual(report.deck_status, "favorável")


if __name__ == "__main__":
    unittest.main()
