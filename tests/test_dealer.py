import unittest

from blackjack_risk_engine.cards import Card, Rank, Suit
from blackjack_risk_engine.dealer import DealerPolicy
from blackjack_risk_engine.hand import Hand
from blackjack_risk_engine.rules import TableRules


class DealerPolicyTests(unittest.TestCase):
    def test_dealer_stands_on_soft_17_by_default(self) -> None:
        hand = Hand([Card(Rank.ACE, Suit.CLUBS), Card(Rank.SIX, Suit.HEARTS)])

        self.assertFalse(DealerPolicy(TableRules()).should_hit(hand))

    def test_dealer_hits_soft_17_when_rule_enabled(self) -> None:
        hand = Hand([Card(Rank.ACE, Suit.CLUBS), Card(Rank.SIX, Suit.HEARTS)])
        rules = TableRules(dealer_hits_soft_17=True)

        self.assertTrue(DealerPolicy(rules).should_hit(hand))


if __name__ == "__main__":
    unittest.main()
