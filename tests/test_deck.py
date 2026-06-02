import unittest

from blackjack_risk_engine.deck import Shoe, standard_deck


class DeckTests(unittest.TestCase):
    def test_standard_deck_has_52_cards(self) -> None:
        self.assertEqual(len(standard_deck()), 52)

    def test_shoe_uses_configured_number_of_decks(self) -> None:
        shoe = Shoe(deck_count=2)

        self.assertEqual(shoe.remaining(), 104)

    def test_draw_removes_one_card(self) -> None:
        shoe = Shoe(deck_count=1)

        shoe.draw()

        self.assertEqual(shoe.remaining(), 51)


if __name__ == "__main__":
    unittest.main()
