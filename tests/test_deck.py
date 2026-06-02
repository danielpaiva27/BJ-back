import unittest

from blackjack_risk_engine.cards import Card, Rank
from blackjack_risk_engine.deck import Shoe, standard_deck


class DeckTests(unittest.TestCase):
    def test_standard_deck_has_52_cards(self) -> None:
        self.assertEqual(len(standard_deck()), 52)

    def test_standard_deck_has_blackjack_value_distribution(self) -> None:
        cards = standard_deck()

        self.assertEqual(cards.count(Card(Rank.ACE)), 4)
        self.assertEqual(cards.count(Card(Rank.TWO)), 4)
        self.assertEqual(cards.count(Card(Rank.NINE)), 4)
        self.assertEqual(cards.count(Card(Rank.TEN)), 16)

    def test_shoe_uses_configured_number_of_decks(self) -> None:
        shoe = Shoe(deck_count=6)

        self.assertEqual(shoe.remaining(), 312)

    def test_draw_removes_one_card(self) -> None:
        shoe = Shoe(deck_count=1)

        shoe.draw()

        self.assertEqual(shoe.remaining(), 51)

    def test_remove_seen_cards_removes_each_seen_card(self) -> None:
        shoe = Shoe(deck_count=1)

        shoe.remove_seen_cards([Card(Rank.ACE), Card(Rank.TEN), Card(Rank.TEN)])

        self.assertEqual(shoe.remaining(), 49)
        self.assertEqual(shoe.cards.count(Card(Rank.ACE)), 3)
        self.assertEqual(shoe.cards.count(Card(Rank.TEN)), 14)

    def test_remove_missing_card_raises_clear_error(self) -> None:
        shoe = Shoe(deck_count=1)

        shoe.remove_seen_cards([Card(Rank.ACE)] * 4)

        with self.assertRaisesRegex(ValueError, "cannot remove card A: not present in shoe"):
            shoe.remove_card(Card(Rank.ACE))


if __name__ == "__main__":
    unittest.main()
