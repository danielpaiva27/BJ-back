from __future__ import annotations

from collections.abc import Iterable

from blackjack_risk_engine.engine_core.action_ev import ActionEvRanking, calculate_action_evs_deterministic
from blackjack_risk_engine.engine_core.state import CoreGameState


def deterministic_analysis(
    state: CoreGameState,
    legal_actions: Iterable[str],
) -> ActionEvRanking:
    return calculate_action_evs_deterministic(state, tuple(legal_actions))
