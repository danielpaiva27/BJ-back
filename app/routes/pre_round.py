from __future__ import annotations

from fastapi import APIRouter, HTTPException

from blackjack_risk_engine.engine_core.pre_round import analyze_pre_round

from app.pre_round_schemas import (
    PreRoundAnalysisRequest,
    PreRoundAnalysisResponse,
)


router = APIRouter(tags=["pre-round"])


@router.post(
    "/pre-round-analysis",
    response_model=PreRoundAnalysisResponse,
    response_model_exclude_none=True,
    summary="Analyze the shoe before a blackjack round",
)
def pre_round_analysis_endpoint(
    payload: PreRoundAnalysisRequest,
) -> dict[str, object]:
    try:
        rules = (
            payload.rules.model_dump(exclude_none=True)
            if payload.rules is not None
            else None
        )
        return analyze_pre_round(
            number_of_decks=payload.number_of_decks,
            seen_cards=payload.seen_cards,
            bankroll=payload.bankroll,
            minimum_bet=payload.minimum_bet,
            rules=rules,
            systems=payload.systems,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
