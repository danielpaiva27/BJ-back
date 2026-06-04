import unittest

from blackjack_risk_engine.engine_core.adapters import build_core_state_from_inputs
from blackjack_risk_engine.engine_core.monte_carlo_analysis import (
    MonteCarloConfig,
    monte_carlo_analysis,
    plan_monte_carlo_chunks,
)
from blackjack_risk_engine.rules import GameRules


class MonteCarloAnalysisTests(unittest.TestCase):
    def test_seed_makes_optimized_monte_carlo_reproducible(self) -> None:
        state = build_core_state_from_inputs(["8", "8"], "10", [], GameRules())
        config = MonteCarloConfig(parallel_enabled=False)

        first = monte_carlo_analysis(state, "split", simulations=500, seed=123, config=config)
        second = monte_carlo_analysis(state, "split", simulations=500, seed=123, config=config)

        self.assertEqual(first.stats, second.stats)
        self.assertFalse(first.used_parallel)

    def test_parallel_and_single_process_are_statistically_close(self) -> None:
        state = build_core_state_from_inputs(["8", "8"], "10", [], GameRules())
        single = monte_carlo_analysis(
            state,
            "split",
            simulations=1200,
            seed=456,
            config=MonteCarloConfig(parallel_enabled=False, simulation_chunk_size=200),
        )
        parallel = monte_carlo_analysis(
            state,
            "split",
            simulations=1200,
            seed=456,
            config=MonteCarloConfig(
                parallel_enabled=True,
                parallel_threshold=1,
                simulation_chunk_size=200,
                max_workers=2,
            ),
        )

        self.assertTrue(parallel.used_parallel)
        self.assertEqual(parallel.chunk_count, 6)
        self.assertLess(abs(single.stats.expected_value - parallel.stats.expected_value), 0.25)

    def test_small_simulation_count_does_not_parallelize(self) -> None:
        state = build_core_state_from_inputs(["8", "8"], "10", [], GameRules())
        result = monte_carlo_analysis(
            state,
            "split",
            simulations=20,
            seed=789,
            config=MonteCarloConfig(
                parallel_enabled=True,
                parallel_threshold=20_000,
                simulation_chunk_size=5,
                max_workers=2,
            ),
        )

        self.assertFalse(result.used_parallel)
        self.assertEqual(result.chunk_count, 4)

    def test_large_simulation_plan_uses_chunks(self) -> None:
        chunks = plan_monte_carlo_chunks(
            45_000,
            MonteCarloConfig(simulation_chunk_size=10_000),
        )

        self.assertEqual(chunks, (10_000, 10_000, 10_000, 10_000, 5_000))

    def test_surrender_result_is_aggregated_like_legacy_monte_carlo(self) -> None:
        state = build_core_state_from_inputs(["10", "6"], "10", [], GameRules(surrender_allowed=True))

        result = monte_carlo_analysis(state, "surrender", simulations=25, seed=321)

        self.assertEqual(result.stats.expected_value, -0.5)
        self.assertEqual(result.stats.losses, 25)
        self.assertEqual(result.stats.wins, 0)
        self.assertEqual(result.stats.pushes, 0)


if __name__ == "__main__":
    unittest.main()
