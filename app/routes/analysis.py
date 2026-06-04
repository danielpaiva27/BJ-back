from __future__ import annotations

from fastapi import APIRouter, HTTPException

from blackjack_risk_engine import __version__
from blackjack_risk_engine.engine_core.adapters import build_core_state_from_inputs
from blackjack_risk_engine.engine_core.monte_carlo_analysis import MonteCarloConfig
from blackjack_risk_engine.ev import analyze_hand
from blackjack_risk_engine.rules import GameRules

from app.schemas import AnalyzeHandRequest


router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "blackjack-risk-engine",
        "version": __version__,
    }


@router.post("/analyze-hand")
def analyze_hand_endpoint(payload: AnalyzeHandRequest) -> dict:
    try:
        rules = GameRules(**payload.rules.model_dump())
        core_state = build_core_state_from_inputs(
            player_hand=payload.player_hand,
            dealer_up_card=payload.dealer_upcard,
            seen_cards=payload.seen_cards,
            rules=rules,
        )
        return analyze_hand(
            player_hand=payload.player_hand,
            dealer_up_card=payload.dealer_upcard,
            seen_cards=payload.seen_cards,
            rules=rules,
            simulations=payload.simulations,
            seed=payload.seed,
            minimum_bet=payload.minimum_bet,
            bankroll=payload.bankroll,
            risk_profile=payload.risk_profile,
            core_state=core_state,
            engine_mode=payload.engine_mode,
            monte_carlo_config=MonteCarloConfig(
                parallel_enabled=payload.monte_carlo_parallel_enabled,
                simulation_chunk_size=payload.simulation_chunk_size,
                max_workers=payload.max_workers,
            ),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
