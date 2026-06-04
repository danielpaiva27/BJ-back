import unittest

from blackjack_risk_engine.engine_core.cards import string_to_rank
from blackjack_risk_engine.engine_core.dealer_dp import (
    dealer_distribution_cache_clear,
    dealer_outcome_distribution,
    stand_ev_from_distribution,
)


def counts_from_cards(cards: list[str]) -> tuple[int, ...]:
    counts = [0] * 10
    for card in cards:
        counts[string_to_rank(card)] += 1
    return tuple(counts)


class DealerDistributionDpTests(unittest.TestCase):
    def setUp(self) -> None:
        dealer_distribution_cache_clear()

    def test_ten_upcard_distribution_can_reach_all_terminal_buckets(self) -> None:
        distribution = dealer_outcome_distribution(
            dealer_upcard_rank=string_to_rank("10"),
            deck_counts=counts_from_cards(["A", "6", "7", "8", "9", "10"]),
            dealer_hits_soft_17=False,
        )

        self.assertAlmostEqual(distribution[0], 6 / 30)
        self.assertAlmostEqual(distribution[1], 5 / 30)
        self.assertAlmostEqual(distribution[2], 5 / 30)
        self.assertAlmostEqual(distribution[3], 5 / 30)
        self.assertAlmostEqual(distribution[4], 5 / 30)
        self.assertAlmostEqual(distribution[5], 4 / 30)

    def test_distribution_sums_to_one_and_has_no_negative_probabilities(self) -> None:
        distribution = dealer_outcome_distribution(
            dealer_upcard_rank=string_to_rank("9"),
            deck_counts=counts_from_cards(["A", "2", "3", "4", "5", "6", "7", "8", "10", "10"]),
            dealer_hits_soft_17=False,
        )

        self.assertAlmostEqual(sum(distribution), 1.0)
        for probability in distribution:
            self.assertGreaterEqual(probability, 0.0)

    def test_dealer_stands_on_soft_17_when_rule_is_false(self) -> None:
        distribution = dealer_outcome_distribution(
            dealer_upcard_rank=string_to_rank("A"),
            deck_counts=counts_from_cards(["2", "6", "10"]),
            dealer_hits_soft_17=False,
        )

        self.assertAlmostEqual(distribution[0], 1 / 3)
        self.assertAlmostEqual(distribution[2], 1 / 3)
        self.assertAlmostEqual(distribution[4], 1 / 3)
        self.assertAlmostEqual(distribution[5], 0.0)

    def test_dealer_hits_soft_17_when_rule_is_true(self) -> None:
        distribution = dealer_outcome_distribution(
            dealer_upcard_rank=string_to_rank("A"),
            deck_counts=counts_from_cards(["2", "6", "10"]),
            dealer_hits_soft_17=True,
        )

        self.assertAlmostEqual(distribution[0], 1 / 6)
        self.assertAlmostEqual(distribution[2], 1 / 2)
        self.assertAlmostEqual(distribution[4], 1 / 3)
        self.assertAlmostEqual(distribution[5], 0.0)

    def test_empty_or_invalid_deck_counts_are_rejected_safely(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one card"):
            dealer_outcome_distribution(string_to_rank("10"), (0, 0, 0, 0, 0, 0, 0, 0, 0, 0), False)

        with self.assertRaisesRegex(ValueError, "exactly 10 ranks"):
            dealer_outcome_distribution(string_to_rank("10"), (1, 2), False)

        with self.assertRaisesRegex(ValueError, "negative"):
            dealer_outcome_distribution(string_to_rank("10"), (1, 1, 1, 1, 1, 1, 1, 1, 1, -1), False)

    def test_stand_ev_from_distribution_compares_player_total_to_dealer(self) -> None:
        result = stand_ev_from_distribution(
            player_total=20,
            distribution=(0.1, 0.1, 0.1, 0.2, 0.1, 0.4),
        )

        self.assertAlmostEqual(result.win_rate, 0.7)
        self.assertAlmostEqual(result.lose_rate, 0.1)
        self.assertAlmostEqual(result.push_rate, 0.2)
        self.assertAlmostEqual(result.expected_value, 0.6)


if __name__ == "__main__":
    unittest.main()
