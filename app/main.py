from __future__ import annotations

from fastapi import FastAPI

from app.routes.analysis import router as analysis_router


app = FastAPI(
    title="blackjack-risk-engine",
    description="API academica/simulacional para analise de decisoes em blackjack.",
    version="0.1.0",
)

app.include_router(analysis_router)
