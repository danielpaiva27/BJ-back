from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from blackjack_risk_engine.engine_core.action_ev import ActionEvRanking, DeterministicEvCacheLimitExceeded
from blackjack_risk_engine.engine_core.deterministic_analysis import deterministic_analysis
from blackjack_risk_engine.engine_core.state import CoreGameState


@dataclass(frozen=True, slots=True)
class HybridAnalysisPlan:
    deterministic_ranking: ActionEvRanking | None
    deterministic_actions: tuple[str, ...]
    monte_carlo_actions: tuple[str, ...]
    deterministic_cache_states: int
    fallback_reason: str | None = None


def hybrid_analysis(
    state: CoreGameState,
    legal_actions: Iterable[str],
) -> HybridAnalysisPlan:
    action_tuple = tuple(legal_actions)
    try:
        ranking = deterministic_analysis(state, action_tuple)
    except DeterministicEvCacheLimitExceeded as error:
        return HybridAnalysisPlan(
            deterministic_ranking=None,
            deterministic_actions=(),
            monte_carlo_actions=action_tuple,
            deterministic_cache_states=0,
            fallback_reason=str(error),
        )

    monte_carlo_actions = ranking.unsupported_actions
    deterministic_actions = tuple(action for action in action_tuple if action not in monte_carlo_actions)
    return HybridAnalysisPlan(
        deterministic_ranking=ranking,
        deterministic_actions=deterministic_actions,
        monte_carlo_actions=monte_carlo_actions,
        deterministic_cache_states=ranking.cache_states,
    )
