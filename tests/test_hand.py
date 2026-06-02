import unittest

from blackjack_risk_engine.cards import Card, Rank, Suit
from blackjack_risk_engine.hand import Hand


class HandTests(unittest.TestCase):
    def test_blackjack_hand(self) -> None:
        hand = Hand([Card(Rank.ACE, Suit.CLUBS), Card(Rank.KING, Suit.HEARTS)])

        self.assertEqual(hand.best_value, 21)
        self.assertTrue(hand.is_blackjack)

    def test_soft_hand_value(self) -> None:
        hand = Hand([Card(Rank.ACE, Suit.CLUBS), Card(Rank.SIX, Suit.HEARTS)])

        self.assertEqual(hand.best_value, 17)
        self.assertTrue(hand.is_soft)

    def test_bust_hand(self) -> None:
        hand = Hand(
            [
                Card(Rank.TEN, Suit.CLUBS),
                Card(Rank.KING, Suit.HEARTS),
                Card(Rank.FIVE, Suit.SPADES),
            ]
        )

        self.assertTrue(hand.is_bust)


if __name__ == "__main__":
    unittest.main()
