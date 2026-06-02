import unittest

from blackjack_risk_engine.decisions import Decision, get_legal_actions
from blackjack_risk_engine.hand import Hand
from blackjack_risk_engine.rules import GameRules


class LegalActionsTests(unittest.TestCase):
    def test_double_is_available_for_initial_two_card_hand_when_allowed(self) -> None:
        actions = get_legal_actions(Hand.from_values(["10", "6"]), GameRules(double_allowed=True))

        self.assertEqual(actions, (Decision.HIT, Decision.STAND, Decision.DOUBLE))

    def test_double_is_not_available_when_rule_disallows_it(self) -> None:
        actions = get_legal_actions(Hand.from_values(["10", "6"]), GameRules(double_allowed=False))

        self.assertEqual(actions, (Decision.HIT, Decision.STAND))

    def test_double_is_not_available_for_more_than_two_cards(self) -> None:
        actions = get_legal_actions(Hand.from_values(["10", "2", "3"]), GameRules(double_allowed=True))

        self.assertEqual(actions, (Decision.HIT, Decision.STAND))

    def test_pair_of_eights_can_split(self) -> None:
        actions = get_legal_actions(Hand.from_values(["8", "8"]), GameRules())

        self.assertIn(Decision.SPLIT, actions)

    def test_ten_value_cards_can_split(self) -> None:
        actions = get_legal_actions(Hand.from_values(["10", "10"]), GameRules())

        self.assertIn(Decision.SPLIT, actions)

    def test_different_hands_cannot_split(self) -> None:
        actions = get_legal_actions(Hand.from_values(["8", "9"]), GameRules())

        self.assertNotIn(Decision.SPLIT, actions)

    def test_split_limit_is_respected(self) -> None:
        actions = get_legal_actions(Hand.from_values(["8", "8"]), GameRules(max_splits=1), splits_done=1)

        self.assertNotIn(Decision.SPLIT, actions)

    def test_surrender_is_available_when_rule_allows_it(self) -> None:
        actions = get_legal_actions(Hand.from_values(["10", "6"]), GameRules(surrender_allowed=True))

        self.assertIn(Decision.SURRENDER, actions)

    def test_surrender_is_not_available_when_rule_disallows_it(self) -> None:
        actions = get_legal_actions(Hand.from_values(["10", "6"]), GameRules(surrender_allowed=False))

        self.assertNotIn(Decision.SURRENDER, actions)

    def test_surrender_is_not_available_after_initial_hand(self) -> None:
        actions = get_legal_actions(Hand.from_values(["10", "2", "3"]), GameRules(surrender_allowed=True))

        self.assertNotIn(Decision.SURRENDER, actions)

    def test_natural_blackjack_only_allows_stand(self) -> None:
        actions = get_legal_actions(Hand.from_values(["A", "10"]), GameRules(surrender_allowed=True))

        self.assertEqual(actions, (Decision.STAND,))


if __name__ == "__main__":
    unittest.main()
