from __future__ import annotations

from fastapi import APIRouter, HTTPException

from blackjack_risk_engine import __version__
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
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
