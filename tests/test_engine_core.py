import unittest

from blackjack_risk_engine.engine_core.adapters import (
    build_core_state_from_inputs,
    core_state_to_public_hand_analysis,
    core_state_to_public_input,
    rank_to_card,
    ranks_to_strings,
)
from blackjack_risk_engine.engine_core.cards import (
    deck_counts_for_decks,
    hi_lo_weight,
    rank_to_string,
    string_to_rank,
)
from blackjack_risk_engine.engine_core.hand import (
    add_card_to_total,
    evaluate_hand_from_ranks,
    is_blackjack_two_cards,
    is_bust,
)
from blackjack_risk_engine.rules import GameRules


class EngineCoreCardTests(unittest.TestCase):
    def test_string_rank_conversion_uses_compact_indices(self) -> None:
        self.assertEqual(string_to_rank("A"), 0)
        self.assertEqual(string_to_rank("2"), 1)
        self.assertEqual(string_to_rank("10"), 9)
        self.assertEqual(rank_to_string(0), "A")
        self.assertEqual(rank_to_string(9), "10")

    def test_invalid_rank_string_raises_public_card_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid blackjack card 'J'"):
            string_to_rank("J")

    def test_hi_lo_weights_are_centralized_by_rank(self) -> None:
        self.assertEqual(hi_lo_weight(string_to_rank("A")), -1)
        self.assertEqual(hi_lo_weight(string_to_rank("5")), 1)
        self.assertEqual(hi_lo_weight(string_to_rank("8")), 0)
        self.assertEqual(hi_lo_weight(string_to_rank("10")), -1)

    def test_deck_counts_for_one_and_six_decks(self) -> None:
        self.assertEqual(deck_counts_for_decks(1), (4, 4, 4, 4, 4, 4, 4, 4, 4, 16))
        self.assertEqual(deck_counts_for_decks(6), (24, 24, 24, 24, 24, 24, 24, 24, 24, 96))

    def test_rank_to_card_bridges_back_to_public_card(self) -> None:
        card = rank_to_card(9)

        self.assertEqual(str(card), "10")
        self.assertEqual(card.value, 10)


class EngineCoreHandTests(unittest.TestCase):
    def test_evaluates_hard_soft_bust_and_blackjack(self) -> None:
        hard = evaluate_hand_from_ranks((string_to_rank("10"), string_to_rank("6")))
        soft = evaluate_hand_from_ranks((string_to_rank("A"), string_to_rank("7")))
        bust = evaluate_hand_from_ranks((string_to_rank("10"), string_to_rank("7"), string_to_rank("6")))
        blackjack = evaluate_hand_from_ranks((string_to_rank("A"), string_to_rank("10")))

        self.assertEqual(hard.total, 16)
        self.assertFalse(hard.is_soft)
        self.assertEqual(soft.total, 18)
        self.assertTrue(soft.is_soft)
        self.assertEqual(bust.total, 23)
        self.assertTrue(bust.is_bust)
        self.assertEqual(blackjack.total, 21)
        self.assertTrue(blackjack.is_blackjack)

    def test_add_card_to_total_tracks_soft_aces(self) -> None:
        total, soft_aces = add_card_to_total(0, 0, string_to_rank("A"))
        total, soft_aces = add_card_to_total(total, soft_aces, string_to_rank("7"))
        total, soft_aces = add_card_to_total(total, soft_aces, string_to_rank("10"))

        self.assertEqual(total, 18)
        self.assertEqual(soft_aces, 0)

    def test_blackjack_and_bust_helpers(self) -> None:
        self.assertTrue(is_blackjack_two_cards((string_to_rank("A"), string_to_rank("10"))))
        self.assertFalse(is_blackjack_two_cards((string_to_rank("A"), string_to_rank("9"), string_to_rank("A"))))
        self.assertTrue(is_bust(22))
        self.assertFalse(is_bust(21))


class EngineCoreStateAdapterTests(unittest.TestCase):
    def test_build_core_state_from_public_inputs_is_hashable_and_compact(self) -> None:
        state = build_core_state_from_inputs(
            player_hand=["A", "10"],
            dealer_up_card="9",
            seen_cards=["2"],
            rules=GameRules(number_of_decks=1),
        )

        self.assertEqual(state.player_ranks, (0, 9))
        self.assertEqual(state.dealer_upcard_rank, 8)
        self.assertEqual(state.seen_ranks, (1,))
        self.assertEqual(state.deck_counts, (3, 3, 4, 4, 4, 4, 4, 4, 3, 15))
        self.assertIsInstance(hash(state), int)

    def test_core_state_public_adapters_preserve_api_strings(self) -> None:
        state = build_core_state_from_inputs(
            player_hand=["8", "8"],
            dealer_up_card="10",
            seen_cards=["A"],
            rules=GameRules(),
        )

        self.assertEqual(core_state_to_public_input(state), {"player": ["8", "8"], "dealer": "10", "seen": ["A"]})
        self.assertEqual(ranks_to_strings(state.player_ranks), ["8", "8"])
        self.assertEqual(
            core_state_to_public_hand_analysis(state),
            {
                "cards": ["8", "8"],
                "total": 16,
                "is_soft": False,
                "is_bust": False,
                "is_blackjack": False,
                "is_pair": True,
                "can_split": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
