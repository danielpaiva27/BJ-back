from __future__ import annotations

import math
from dataclasses import replace

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from blackjack_risk_engine.engine_core.pre_round import analyze_pre_round
from blackjack_risk_engine.engine_core.pre_round.machine_ev import (
    MachineEvConfig,
    MachineEvInput,
    MachineEvResult,
    evaluate_machine_ev_pre_round,
)

from app.pre_round_schemas import (
    MachineEvDebugMetricsResponse,
    MachineEvPreRoundRequest,
    MachineEvPreRoundResponse,
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


@router.post(
    "/pre-round-analysis/machine-ev",
    response_model=MachineEvPreRoundResponse,
    summary="Estimate next-hand EV from the remaining shoe composition",
)
def machine_ev_pre_round_endpoint(
    payload: MachineEvPreRoundRequest,
) -> JSONResponse:
    try:
        rules = _machine_ev_rules(payload)
        config = MachineEvConfig()
        config = replace(
            config,
            decision_engine_mode=payload.engine_mode or config.decision_engine_mode,
            include_debug_metrics=payload.include_debug_metrics,
            max_duration_ms=payload.max_duration_ms or config.max_duration_ms,
        )
        result = evaluate_machine_ev_pre_round(
            MachineEvInput(
                number_of_decks=payload.number_of_decks,
                seen_cards=tuple(payload.seen_cards),
                bankroll=payload.bankroll,
                minimum_bet=payload.minimum_bet,
                rules=rules,
            ),
            config,
        )
        response = _machine_ev_response(
            result,
            include_debug_metrics=payload.include_debug_metrics,
        )
        excluded_fields = (
            set()
            if payload.include_debug_metrics
            else {"debug_metrics"}
        )
        return JSONResponse(
            content=response.model_dump(exclude=excluded_fields),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _machine_ev_rules(
    payload: MachineEvPreRoundRequest,
) -> dict[str, object] | None:
    if payload.rules is None:
        return None

    rules = payload.rules.model_dump(exclude_none=True)
    payout = rules.get("blackjack_payout")
    if isinstance(payout, (int, float)) and not isinstance(payout, bool):
        if math.isclose(float(payout), 1.5, rel_tol=0.0, abs_tol=1e-9):
            rules["blackjack_payout"] = "3:2"
        elif math.isclose(float(payout), 1.2, rel_tol=0.0, abs_tol=1e-9):
            rules["blackjack_payout"] = "6:5"
    return rules


def _machine_ev_response(
    result: MachineEvResult,
    *,
    include_debug_metrics: bool,
) -> MachineEvPreRoundResponse:
    edge = result.summary.estimated_next_hand_edge
    if edge is None:
        raise ValueError("Machine EV result does not contain an estimated edge")

    debug_metrics = None
    if include_debug_metrics:
        duration_ms = result.metrics.duration_ms
        if duration_ms is None:
            raise ValueError("Machine EV result does not contain duration metrics")
        debug_metrics = MachineEvDebugMetricsResponse(
            states_evaluated=result.metrics.states_evaluated,
            duration_ms=duration_ms,
            cache_hits=result.metrics.cache_hits,
            cache_misses=result.metrics.cache_misses,
            timed_out=result.metrics.timed_out,
            warnings=list(result.metrics.warnings),
            precision_mode=(
                result.config.precision_mode
                if result.config is not None
                else MachineEvConfig().precision_mode
            ),
        )

    return MachineEvPreRoundResponse(
        model_id=result.summary.model_id,
        label=result.summary.label,
        model_type=result.summary.model_type,
        is_human_replicable=result.summary.is_human_replicable,
        estimated_next_hand_edge=edge,
        risk_if_minimum_bet=result.summary.risk_if_minimum_bet,
        minimum_bankroll_required_for_minimum_bet=(
            result.summary.minimum_bankroll_required_for_minimum_bet
        ),
        recommendation_status=result.summary.recommendation_status,
        recommendation_text=result.summary.recommendation_text,
        debug_metrics=debug_metrics,
    )
