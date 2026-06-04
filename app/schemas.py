from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


CardValue = Literal["A", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
RiskProfileValue = Literal["conservative", "moderate", "aggressive"]


class RulesPayload(BaseModel):
    number_of_decks: int = Field(default=6, gt=0)
    dealer_hits_soft_17: bool = False
    blackjack_payout: Literal["3:2", "6:5"] = "3:2"
    double_allowed: bool = True
    double_after_split: bool = True
    surrender_allowed: bool = False
    max_splits: int = Field(default=3, ge=0)
    dealer_peek: bool = True
    hit_split_aces: bool = False
    resplit_aces: bool = False


class AnalyzeHandRequest(BaseModel):
    player_hand: list[CardValue] = Field(min_length=2)
    dealer_upcard: CardValue
    seen_cards: list[CardValue] = Field(default_factory=list)
    rules: RulesPayload = Field(default_factory=RulesPayload)
    engine_mode: Literal["legacy", "deterministic", "hybrid", "monte_carlo"] | None = None
    simulations: int = Field(default=10_000, gt=0)
    seed: int | None = None
    max_workers: int | None = Field(default=None, gt=0)
    monte_carlo_parallel_enabled: bool = False
    simulation_chunk_size: int = Field(default=10_000, gt=0)
    bankroll: float = Field(default=1000.0, gt=0)
    minimum_bet: float = Field(default=10.0, gt=0)
    risk_profile: RiskProfileValue = "moderate"

    @field_validator("player_hand", "seen_cards", mode="before")
    @classmethod
    def normalize_card_list(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [str(card).strip().upper() for card in value]

    @field_validator("dealer_upcard", mode="before")
    @classmethod
    def normalize_card(cls, value: object) -> object:
        if value is None:
            return value
        return str(value).strip().upper()
