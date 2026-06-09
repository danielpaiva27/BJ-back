import math
import unittest

from blackjack_risk_engine.engine_core.action_ev import (
    calculate_action_evs_deterministic,
    ev_double,
    ev_hit,
    ev_stand,
    ev_surrender,
)
from blackjack_risk_engine.engine_core.adapters import build_core_state_from_inputs
from blackjack_risk_engine.engine_core.cards import string_to_rank
from blackjack_risk_engine.engine_core.hand import evaluate_hand_from_ranks
from blackjack_risk_engine.engine_core.rules import CoreRules
from blackjack_risk_engine.rules import GameRules


def counts_from_cards(cards: list[str]) -> tuple[int, ...]:
    counts = [0] * 10
    for card in cards:
        counts[string_to_rank(card)] += 1
    return tuple(counts)


class ActionEvTests(unittest.TestCase):
    def test_stand_ev_uses_dealer_distribution(self) -> None:
        result = ev_stand(
            player_total=20,
            dealer_upcard_rank=string_to_rank("10"),
            deck_counts=counts_from_cards(["7", "8", "9", "10", "10"]),
            rules=CoreRules(),
        )

        self.assertGreater(result.expected_value, 0)
        self.assertAlmostEqual(result.win_rate + result.lose_rate + result.push_rate, 1.0)

    def test_hit_ev_recurses_without_double_or_surrender_after_hit(self) -> None:
        state = build_core_state_from_inputs(
            player_hand=["10", "2"],
            dealer_up_card="10",
            seen_cards=[],
            rules=GameRules(number_of_decks=1),
        )
        player = evaluate_hand_from_ranks(state.player_ranks)

        result = ev_hit(
            player_total=player.total,
            soft_aces=player.soft_aces,
            dealer_upcard_rank=state.dealer_upcard_rank,
            deck_counts=state.deck_counts,
            rules=state.rules,
        )

        self.assertGreaterEqual(result.win_rate, 0)
        self.assertLessEqual(result.win_rate, 1)
        self.assertAlmostEqual(result.win_rate + result.lose_rate + result.push_rate, 1.0)

    def test_double_ev_draws_one_card_then_stands_with_multiplier(self) -> None:
        state = build_core_state_from_inputs(
            player_hand=["10", "6"],
            dealer_up_card="10",
            seen_cards=[],
            rules=GameRules(number_of_decks=1),
        )
        player = evaluate_hand_from_ranks(state.player_ranks)

        result = ev_double(
            player_total=player.total,
            soft_aces=player.soft_aces,
            dealer_upcard_rank=state.dealer_upcard_rank,
            deck_counts=state.deck_counts,
            rules=state.rules,
        )

        self.assertGreaterEqual(result.std_dev, 0)
        self.assertGreaterEqual(result.second_moment, result.expected_value * result.expected_value)

    def test_double_ev_accounts_for_dealer_natural_before_double_multiplier(self) -> None:
        result = ev_double(
            player_total=11,
            soft_aces=0,
            dealer_upcard_rank=string_to_rank("10"),
            deck_counts=counts_from_cards(["A", "A", "A"]),
            rules=CoreRules(),
        )

        self.assertAlmostEqual(result.expected_value, -1.0)
        self.assertGreater(result.expected_value, -2.0)
        self.assertEqual(result.lose_rate, 1.0)
        self.assertAlmostEqual(result.second_moment, 1.0)
        self.assertTrue(math.isfinite(result.expected_value))
        self.assertTrue(math.isfinite(result.std_dev))

    def test_surrender_ev_is_minus_half_when_allowed(self) -> None:
        result = ev_surrender(CoreRules(surrender_allowed=True))

        self.assertEqual(result.expected_value, -0.5)
        self.assertEqual(result.lose_rate, 1.0)
        self.assertEqual(result.std_dev, 0.0)

    def test_surrender_ev_rejects_when_not_allowed(self) -> None:
        with self.assertRaisesRegex(ValueError, "surrender is not allowed"):
            ev_surrender(CoreRules(surrender_allowed=False))

    def test_ranking_returns_best_action_and_marks_split_unsupported(self) -> None:
        state = build_core_state_from_inputs(
            player_hand=["8", "8"],
            dealer_up_card="10",
            seen_cards=[],
            rules=GameRules(),
        )

        ranking = calculate_action_evs_deterministic(
            state,
            legal_actions=("hit", "stand", "double", "split"),
        )

        self.assertEqual(ranking.method, "deterministic_dp")
        self.assertEqual(ranking.unsupported_actions, ("split",))
        self.assertEqual(ranking.actions[0].action, "hit")
        self.assertGreater(ranking.cache_states, 0)


if __name__ == "__main__":
    unittest.main()
