import unittest
from dataclasses import dataclass, field

from blackjack_risk_engine.cards import Card, Rank
from blackjack_risk_engine.dealer import DealerPolicy, play_dealer_hand
from blackjack_risk_engine.hand import Hand
from blackjack_risk_engine.rules import GameRules


@dataclass(slots=True)
class ControlledDeck:
    cards: list[Card] = field(default_factory=list)

    @classmethod
    def from_values(cls, values: list[str]) -> "ControlledDeck":
        return cls([Card(Rank(value)) for value in values])

    def draw(self) -> Card:
        if not self.cards:
            raise IndexError("controlled deck is empty")
        return self.cards.pop(0)


class DealerPolicyTests(unittest.TestCase):
    def test_dealer_stands_on_soft_17_by_default(self) -> None:
        hand = Hand([Card(Rank.ACE), Card(Rank.SIX)])

        self.assertFalse(DealerPolicy(GameRules()).should_hit(hand))

    def test_dealer_hits_soft_17_when_rule_enabled(self) -> None:
        hand = Hand([Card(Rank.ACE), Card(Rank.SIX)])
        rules = GameRules(dealer_hits_soft_17=True)

        self.assertTrue(DealerPolicy(rules).should_hit(hand))

    def test_dealer_with_16_hits(self) -> None:
        deck = ControlledDeck.from_values(["6", "2"])

        result = play_dealer_hand("10", deck, GameRules())

        self.assertEqual(result.cards, ["10", "6", "2"])
        self.assertEqual(result.total, 18)
        self.assertFalse(result.is_bust)
        self.assertEqual([str(card) for card in result.drawn_cards], ["2"])

    def test_dealer_stands_on_hard_17(self) -> None:
        deck = ControlledDeck.from_values(["7"])

        result = play_dealer_hand("10", deck, GameRules())

        self.assertEqual(result.cards, ["10", "7"])
        self.assertEqual(result.total, 17)
        self.assertFalse(result.is_soft)
        self.assertEqual(deck.cards, [])

    def test_dealer_stands_on_soft_17_when_rule_is_false(self) -> None:
        deck = ControlledDeck.from_values(["6"])

        result = play_dealer_hand("A", deck, GameRules(dealer_hits_soft_17=False))

        self.assertEqual(result.cards, ["A", "6"])
        self.assertEqual(result.total, 17)
        self.assertTrue(result.is_soft)
        self.assertEqual(result.drawn_cards, ())

    def test_dealer_hits_soft_17_when_rule_is_true(self) -> None:
        deck = ControlledDeck.from_values(["6", "2"])

        result = play_dealer_hand("A", deck, GameRules(dealer_hits_soft_17=True))

        self.assertEqual(result.cards, ["A", "6", "2"])
        self.assertEqual(result.total, 19)
        self.assertTrue(result.is_soft)
        self.assertEqual([str(card) for card in result.drawn_cards], ["2"])

    def test_dealer_hits_soft_17_and_converts_to_hard_17_with_ten(self) -> None:
        deck = ControlledDeck.from_values(["6", "10"])

        result = play_dealer_hand("A", deck, GameRules(dealer_hits_soft_17=True))

        self.assertEqual(result.cards, ["A", "6", "10"])
        self.assertEqual(result.total, 17)
        self.assertFalse(result.is_soft)
        self.assertEqual([str(card) for card in result.drawn_cards], ["10"])

    def test_dealer_busts_correctly(self) -> None:
        deck = ControlledDeck.from_values(["6", "10"])

        result = play_dealer_hand("10", deck, GameRules())

        self.assertEqual(result.cards, ["10", "6", "10"])
        self.assertEqual(result.total, 26)
        self.assertTrue(result.is_bust)


if __name__ == "__main__":
    unittest.main()
