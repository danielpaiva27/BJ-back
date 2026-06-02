import unittest

from blackjack_risk_engine.hand import Hand


class HandTests(unittest.TestCase):
    def test_hard_16(self) -> None:
        hand = Hand.from_values(["10", "6"])

        self.assertEqual(hand.card_values, ["10", "6"])
        self.assertEqual(hand.total, 16)
        self.assertFalse(hand.is_soft)
        self.assertFalse(hand.is_bust)
        self.assertFalse(hand.is_blackjack)
        self.assertFalse(hand.is_pair)
        self.assertFalse(hand.can_split)

    def test_soft_18(self) -> None:
        hand = Hand.from_values(["A", "7"])

        self.assertEqual(hand.total, 18)
        self.assertTrue(hand.is_soft)
        self.assertFalse(hand.is_bust)

    def test_ace_adjusts_from_soft_to_hard(self) -> None:
        hand = Hand.from_values(["A", "9", "5"])

        self.assertEqual(hand.total, 15)
        self.assertFalse(hand.is_soft)
        self.assertFalse(hand.is_bust)

    def test_bust_hand(self) -> None:
        hand = Hand.from_values(["10", "7", "6"])

        self.assertEqual(hand.total, 23)
        self.assertTrue(hand.is_bust)

    def test_natural_blackjack(self) -> None:
        hand = Hand.from_values(["A", "10"])

        self.assertEqual(hand.total, 21)
        self.assertTrue(hand.is_soft)
        self.assertTrue(hand.is_blackjack)

    def test_pair_can_split(self) -> None:
        hand = Hand.from_values(["8", "8"])

        self.assertEqual(hand.total, 16)
        self.assertTrue(hand.is_pair)
        self.assertTrue(hand.can_split)

    def test_invalid_card_value_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid blackjack card 'J'"):
            Hand.from_values(["J"])


if __name__ == "__main__":
    unittest.main()
