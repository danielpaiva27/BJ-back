import unittest

from blackjack_risk_engine.cards import Card, Rank, Suit
from blackjack_risk_engine.counting import hi_lo_value, running_count, true_count


class CountingTests(unittest.TestCase):
    def test_hi_lo_values(self) -> None:
        self.assertEqual(hi_lo_value(Card(Rank.TWO, Suit.CLUBS)), 1)
        self.assertEqual(hi_lo_value(Card(Rank.SEVEN, Suit.CLUBS)), 0)
        self.assertEqual(hi_lo_value(Card(Rank.ACE, Suit.CLUBS)), -1)

    def test_running_and_true_count(self) -> None:
        cards = [
            Card(Rank.TWO, Suit.CLUBS),
            Card(Rank.FIVE, Suit.DIAMONDS),
            Card(Rank.KING, Suit.HEARTS),
        ]

        self.assertEqual(running_count(cards), 1)
        self.assertEqual(true_count(4, decks_remaining=2), 2)


if __name__ == "__main__":
    unittest.main()
