import unittest

from blackjack_risk_engine.cards import Card, Rank
from blackjack_risk_engine.decisions import Decision
from blackjack_risk_engine.hand import Hand
from blackjack_risk_engine.rules import GameRules
from blackjack_risk_engine.strategy import choose_continuation_action, recommend_basic_strategy


class StrategyTests(unittest.TestCase):
    def test_hard_12_stands_against_dealer_6(self) -> None:
        action = choose_continuation_action(Hand.from_values(["10", "2"]), Card(Rank.SIX))

        self.assertEqual(action, Decision.STAND)

    def test_hard_12_hits_against_dealer_10(self) -> None:
        action = choose_continuation_action(Hand.from_values(["10", "2"]), Card(Rank.TEN))

        self.assertEqual(action, Decision.HIT)

    def test_hard_16_stands_against_dealer_5(self) -> None:
        action = choose_continuation_action(Hand.from_values(["10", "6"]), Card(Rank.FIVE))

        self.assertEqual(action, Decision.STAND)

    def test_hard_16_hits_against_dealer_10(self) -> None:
        action = choose_continuation_action(Hand.from_values(["10", "6"]), Card(Rank.TEN))

        self.assertEqual(action, Decision.HIT)

    def test_soft_18_stands_against_dealer_6(self) -> None:
        action = choose_continuation_action(Hand.from_values(["A", "7"]), Card(Rank.SIX))

        self.assertEqual(action, Decision.STAND)

    def test_soft_18_hits_against_dealer_10(self) -> None:
        action = choose_continuation_action(Hand.from_values(["A", "7"]), Card(Rank.TEN))

        self.assertEqual(action, Decision.HIT)

    def test_policy_returns_only_valid_continuation_actions(self) -> None:
        for hand in (Hand.from_values(["5", "6"]), Hand.from_values(["10", "6"]), Hand.from_values(["A", "7"])):
            self.assertIn(choose_continuation_action(hand, Card(Rank.TEN)), {Decision.HIT, Decision.STAND})

    def test_basic_strategy_hard_16_against_10_hits_without_surrender(self) -> None:
        action = recommend_basic_strategy(Hand.from_values(["10", "6"]), Card(Rank.TEN), GameRules())

        self.assertEqual(action, Decision.HIT)

    def test_basic_strategy_hard_16_against_10_surrenders_when_allowed(self) -> None:
        action = recommend_basic_strategy(
            Hand.from_values(["10", "6"]),
            Card(Rank.TEN),
            GameRules(surrender_allowed=True),
        )

        self.assertEqual(action, Decision.SURRENDER)

    def test_basic_strategy_11_against_6_doubles(self) -> None:
        action = recommend_basic_strategy(Hand.from_values(["5", "6"]), Card(Rank.SIX), GameRules())

        self.assertEqual(action, Decision.DOUBLE)

    def test_basic_strategy_soft_18_against_9_hits(self) -> None:
        action = recommend_basic_strategy(Hand.from_values(["A", "7"]), Card(Rank.NINE), GameRules())

        self.assertEqual(action, Decision.HIT)

    def test_basic_strategy_pair_8s_against_6_splits(self) -> None:
        action = recommend_basic_strategy(Hand.from_values(["8", "8"]), Card(Rank.SIX), GameRules())

        self.assertEqual(action, Decision.SPLIT)

    def test_basic_strategy_pair_10s_against_6_stands(self) -> None:
        action = recommend_basic_strategy(Hand.from_values(["10", "10"]), Card(Rank.SIX), GameRules())

        self.assertEqual(action, Decision.STAND)


if __name__ == "__main__":
    unittest.main()
