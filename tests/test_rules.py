import unittest

from blackjack_risk_engine.rules import GameRules, TableRules


class GameRulesTests(unittest.TestCase):
    def test_default_rules_are_common_table_defaults(self) -> None:
        rules = GameRules()

        self.assertEqual(rules.number_of_decks, 6)
        self.assertFalse(rules.dealer_hits_soft_17)
        self.assertEqual(rules.blackjack_payout, "3:2")
        self.assertEqual(rules.blackjack_payout_multiplier, 1.5)
        self.assertTrue(rules.double_allowed)
        self.assertTrue(rules.double_after_split)
        self.assertFalse(rules.surrender_allowed)
        self.assertEqual(rules.max_splits, 3)
        self.assertTrue(rules.dealer_peek)
        self.assertFalse(rules.hit_split_aces)
        self.assertFalse(rules.resplit_aces)

    def test_blackjack_payout_accepts_supported_formats(self) -> None:
        three_to_two = GameRules(blackjack_payout="3:2")
        six_to_five = GameRules(blackjack_payout="6:5")

        self.assertEqual(three_to_two.blackjack_payout_multiplier, 1.5)
        self.assertEqual(six_to_five.blackjack_payout_multiplier, 1.2)

    def test_blackjack_payout_rejects_unsupported_formats(self) -> None:
        with self.assertRaisesRegex(ValueError, "blackjack_payout must be one of: 3:2, 6:5"):
            GameRules(blackjack_payout="2:1")

    def test_invalid_number_of_decks_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "number_of_decks must be a positive integer"):
            GameRules(number_of_decks=0)

    def test_invalid_max_splits_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_splits must be a non-negative integer"):
            GameRules(max_splits=-1)

    def test_boolean_fields_must_be_boolean(self) -> None:
        with self.assertRaisesRegex(ValueError, "dealer_peek must be a boolean"):
            GameRules(dealer_peek="yes")

    def test_resplit_aces_requires_splits(self) -> None:
        with self.assertRaisesRegex(ValueError, "resplit_aces requires max_splits"):
            GameRules(max_splits=0, resplit_aces=True)

    def test_table_rules_alias_remains_available(self) -> None:
        self.assertIs(TableRules, GameRules)


if __name__ == "__main__":
    unittest.main()
