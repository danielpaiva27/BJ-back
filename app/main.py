from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from blackjack_risk_engine import __version__

from app.routes.analysis import router as analysis_router
from app.routes.pre_round import router as pre_round_router


app = FastAPI(
    title="blackjack-risk-engine",
    description="API academica/simulacional para analise de decisoes em blackjack.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "Origin", "X-Requested-With"],
)

app.include_router(analysis_router)
app.include_router(pre_round_router)
