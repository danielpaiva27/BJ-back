import unittest
from dataclasses import dataclass, field

from blackjack_risk_engine.cards import Card, Rank
from blackjack_risk_engine.rules import GameRules
from blackjack_risk_engine.simulation import simulate_round


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


class RoundSimulationTests(unittest.TestCase):
    def test_stand_player_beats_dealer(self) -> None:
        deck = ControlledDeck.from_values(["7"])

        result = simulate_round(["10", "8"], "10", deck, GameRules(), "stand")

        self.assertEqual(result.player_hand.card_values, ["10", "8"])
        self.assertEqual(result.dealer_hand.card_values, ["10", "7"])
        self.assertEqual(result.outcome, 1)

    def test_stand_pushes_equal_totals(self) -> None:
        deck = ControlledDeck.from_values(["7"])

        result = simulate_round(["10", "7"], "10", deck, GameRules(), "stand")

        self.assertEqual(result.outcome, 0)

    def test_stand_player_loses_to_higher_dealer_total(self) -> None:
        deck = ControlledDeck.from_values(["7"])

        result = simulate_round(["10", "6"], "10", deck, GameRules(), "stand")

        self.assertEqual(result.outcome, -1)

    def test_hit_player_busts_and_loses(self) -> None:
        deck = ControlledDeck.from_values(["7", "10"])

        result = simulate_round(["10", "6"], "9", deck, GameRules(), "hit")

        self.assertEqual(result.player_hand.card_values, ["10", "6", "10"])
        self.assertTrue(result.player_hand.is_bust)
        self.assertEqual(result.outcome, -1)
        self.assertEqual(result.dealer_hand.card_values, ["9", "7"])

    def test_hit_uses_strategic_policy_until_player_stands(self) -> None:
        deck = ControlledDeck.from_values(["6", "4", "8", "7"])

        result = simulate_round(["2", "3"], "10", deck, GameRules(), "hit")

        self.assertEqual(result.player_hand.card_values, ["2", "3", "4", "8"])
        self.assertEqual(result.player_hand.total, 17)
        self.assertEqual(result.dealer_hand.card_values, ["10", "6", "7"])
        self.assertTrue(result.dealer_hand.is_bust)
        self.assertEqual(result.outcome, 1)

    def test_hit_continuation_uses_dealer_card_strategy(self) -> None:
        deck = ControlledDeck.from_values(["10", "2", "10"])

        result = simulate_round(["5", "5"], "6", deck, GameRules(), "hit")

        self.assertEqual(result.player_hand.card_values, ["5", "5", "2"])
        self.assertEqual(result.player_hand.total, 12)
        self.assertEqual(result.dealer_hand.card_values, ["6", "10", "10"])
        self.assertEqual(result.outcome, 1)

    def test_natural_blackjack_pays_three_to_two(self) -> None:
        deck = ControlledDeck.from_values(["7"])

        result = simulate_round(["A", "10"], "9", deck, GameRules(), "stand")

        self.assertEqual(result.outcome, 1.5)
        self.assertEqual(result.dealer_hand.card_values, ["9", "7"])

    def test_natural_blackjack_pays_six_to_five(self) -> None:
        deck = ControlledDeck.from_values(["7"])
        rules = GameRules(blackjack_payout="6:5")

        result = simulate_round(["A", "10"], "9", deck, rules, "stand")

        self.assertEqual(result.outcome, 1.2)

    def test_mutual_natural_blackjack_pushes(self) -> None:
        deck = ControlledDeck.from_values(["10"])

        result = simulate_round(["A", "10"], "A", deck, GameRules(), "stand")

        self.assertEqual(result.outcome, 0)

    def test_dealer_natural_blackjack_beats_non_natural_player(self) -> None:
        deck = ControlledDeck.from_values(["10"])

        result = simulate_round(["10", "9"], "A", deck, GameRules(), "stand")

        self.assertEqual(result.outcome, -1)

    def test_double_against_dealer_natural_loses_one_unit_before_player_draw(self) -> None:
        deck = ControlledDeck.from_values(["A", "5"])

        result = simulate_round(["5", "6"], "10", deck, GameRules(), "double")

        self.assertEqual(result.player_hand.card_values, ["5", "6"])
        self.assertEqual(result.dealer_hand.card_values, ["10", "A"])
        self.assertEqual(result.outcome, -1)
        self.assertEqual([str(card) for card in deck.cards], ["5"])

    def test_double_win_is_worth_two_units(self) -> None:
        deck = ControlledDeck.from_values(["7", "5"])

        result = simulate_round(["10", "6"], "10", deck, GameRules(), "double")

        self.assertEqual(result.player_hand.card_values, ["10", "6", "5"])
        self.assertEqual(result.dealer_hand.card_values, ["10", "7"])
        self.assertEqual(result.outcome, 2)

    def test_double_loss_is_worth_two_units(self) -> None:
        deck = ControlledDeck.from_values(["9", "2"])

        result = simulate_round(["10", "6"], "10", deck, GameRules(), "double")

        self.assertEqual(result.player_hand.card_values, ["10", "6", "2"])
        self.assertEqual(result.dealer_hand.card_values, ["10", "9"])
        self.assertEqual(result.outcome, -2)

    def test_double_is_rejected_when_rule_disallows_it(self) -> None:
        deck = ControlledDeck.from_values(["7", "5"])

        with self.assertRaisesRegex(ValueError, "action double is not legal"):
            simulate_round(["10", "6"], "10", deck, GameRules(double_allowed=False), "double")

    def test_double_is_rejected_for_more_than_two_card_hand(self) -> None:
        deck = ControlledDeck.from_values(["7", "5"])

        with self.assertRaisesRegex(ValueError, "action double is not legal"):
            simulate_round(["10", "2", "3"], "10", deck, GameRules(), "double")

    def test_split_returns_sum_of_two_hand_results(self) -> None:
        deck = ControlledDeck.from_values(["7", "2", "10", "7"])

        result = simulate_round(["8", "8"], "10", deck, GameRules(), "split")

        self.assertEqual([hand.card_values for hand in result.split_hands], [["8", "2", "7"], ["8", "10"]])
        self.assertEqual(result.dealer_hand.card_values, ["10", "7"])
        self.assertEqual(result.outcome, 1)

    def test_split_ten_value_pair_is_allowed(self) -> None:
        deck = ControlledDeck.from_values(["7", "7", "7"])

        result = simulate_round(["10", "10"], "10", deck, GameRules(), "split")

        self.assertEqual([hand.card_values for hand in result.split_hands], [["10", "7"], ["10", "7"]])
        self.assertEqual(result.outcome, 0)

    def test_split_is_rejected_for_different_cards(self) -> None:
        deck = ControlledDeck.from_values(["7", "2", "10"])

        with self.assertRaisesRegex(ValueError, "action split is not legal"):
            simulate_round(["8", "9"], "10", deck, GameRules(), "split")

    def test_split_limit_is_respected(self) -> None:
        deck = ControlledDeck.from_values(["7", "2", "10"])

        with self.assertRaisesRegex(ValueError, "action split is not legal"):
            simulate_round(["8", "8"], "10", deck, GameRules(max_splits=1), "split", splits_done=1)

    def test_surrender_result_is_always_minus_half(self) -> None:
        deck = ControlledDeck.from_values(["10"])

        result = simulate_round(["10", "6"], "10", deck, GameRules(surrender_allowed=True), "surrender")

        self.assertEqual(result.player_hand.card_values, ["10", "6"])
        self.assertEqual(result.dealer_hand.card_values, ["10", "10"])
        self.assertEqual(result.outcome, -0.5)

    def test_surrender_ends_hand_without_triggering_dealer_draws(self) -> None:
        deck = ControlledDeck.from_values(["10", "2", "3"])
        cards_before = len(deck.cards)

        result = simulate_round(["10", "6"], "10", deck, GameRules(surrender_allowed=True), "surrender")

        self.assertEqual(result.action.value, "surrender")
        self.assertEqual(result.outcome, -0.5)
        self.assertEqual(result.dealer_hand.card_values, ["10", "10"])
        self.assertEqual(result.dealer_result.drawn_cards, ())
        self.assertEqual(result.dealer_result.final_hand.card_values, ["10", "10"])
        self.assertEqual(len(deck.cards), cards_before - 1)
        self.assertEqual([str(card) for card in deck.cards], ["2", "3"])

    def test_surrender_is_rejected_when_rule_disallows_it(self) -> None:
        deck = ControlledDeck.from_values(["10"])

        with self.assertRaisesRegex(ValueError, "action surrender is not legal"):
            simulate_round(["10", "6"], "10", deck, GameRules(surrender_allowed=False), "surrender")

    def test_invalid_action_raises_clear_error(self) -> None:
        deck = ControlledDeck.from_values(["7"])

        with self.assertRaisesRegex(ValueError, "action must be one of: hit, stand, double, split, surrender"):
            simulate_round(["10", "8"], "10", deck, GameRules(), "insurance")


if __name__ == "__main__":
    unittest.main()
