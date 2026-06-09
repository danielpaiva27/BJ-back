from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, FiniteFloat, field_validator


CardValue = Literal["A", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
CountSystemId = Literal["hi_lo", "hi_opt_ii", "wong_halves"]
RecommendationStatus = Literal[
    "observe",
    "marginal_observe",
    "positive_edge_minimum_bet_exceeds_risk_cap",
    "minimum_unit",
    "favorable_risk_capped",
    "favorable_controlled",
    "favorable_bankroll_limited",
    "invalid_bankroll",
    "invalid_minimum_bet",
    "insufficient_bankroll",
]


class PreRoundRulesPayload(BaseModel):
    dealer_hits_soft_17: bool | None = None
    blackjack_payout: Literal["3:2", "6:5"] | FiniteFloat | None = None
    double_allowed: bool | None = None
    double_after_split: bool | None = None
    surrender_allowed: bool | None = None
    max_splits: int | None = Field(default=None, ge=0)
    dealer_peek: bool | None = None
    hit_split_aces: bool | None = None
    resplit_aces: bool | None = None


class PreRoundAnalysisRequest(BaseModel):
    number_of_decks: int = Field(gt=0, strict=True)
    seen_cards: list[CardValue]
    bankroll: FiniteFloat
    minimum_bet: FiniteFloat
    rules: PreRoundRulesPayload | None = None
    systems: list[str] | None = None

    @field_validator("seen_cards", mode="before")
    @classmethod
    def normalize_seen_cards(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [str(card).strip().upper() for card in value]

    @field_validator("systems", mode="before")
    @classmethod
    def normalize_system_ids(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [
            str(system_id).strip().lower()
            for system_id in value
        ]


class BankrollPolicyResponse(BaseModel):
    policy_id: str
    policy_label: str
    description: str
    variance_per_unit: FiniteFloat
    risk_of_ruin_limit: FiniteFloat = Field(gt=0, lt=1)
    max_single_round_exposure: FiniteFloat = Field(gt=0, le=1)
    max_bankroll_exposure: FiniteFloat
    risk_model: str
    safety_kelly_fraction: FiniteFloat | None = None


class AceSideCountResponse(BaseModel):
    total_aces: int
    seen_aces: int
    aces_remaining: int
    expected_aces_remaining: FiniteFloat
    excess_aces: FiniteFloat


class PreRoundSystemResult(BaseModel):
    system_id: CountSystemId
    label: str
    level: int
    balanced: bool
    ace_reckoned: bool
    fractional: bool
    requires_ace_side_count: bool
    running_count: int | FiniteFloat
    true_count: FiniteFloat
    betting_true_count: FiniteFloat
    estimated_player_edge: FiniteFloat
    should_enter: bool
    suggested_units: int = Field(ge=0)
    suggested_amount: FiniteFloat = Field(ge=0)
    bankroll_exposure_percent: FiniteFloat = Field(ge=0)
    max_protected_amount: FiniteFloat = Field(ge=0)
    estimated_risk_of_ruin: FiniteFloat = Field(ge=0, le=1)
    risk_of_ruin_limit: FiniteFloat = Field(gt=0, lt=1)
    risk_model: str
    variance_per_unit: FiniteFloat = Field(gt=0)
    max_bet_by_risk: FiniteFloat = Field(ge=0)
    max_single_round_exposure: FiniteFloat = Field(gt=0, le=1)
    max_bet_by_exposure: FiniteFloat = Field(ge=0)
    selected_bet_fraction: FiniteFloat = Field(ge=0)
    kelly_fraction: FiniteFloat = Field(ge=0)
    risk_limited_fraction: FiniteFloat = Field(ge=0)
    risk_if_minimum_bet: FiniteFloat | None = Field(default=None, ge=0, le=1)
    minimum_bankroll_required_for_minimum_bet: FiniteFloat | None = Field(
        default=None,
        ge=0,
    )
    minimum_bet_exceeds_risk_cap: bool = False
    recommendation_status: RecommendationStatus
    recommendation_text: str
    warnings: list[str]
    cards_seen: int = Field(ge=0)
    cards_remaining: int = Field(ge=0)
    decks_remaining: FiniteFloat = Field(ge=0)
    scale: int | None = Field(default=None, gt=0)
    scaled_running_count: int | None = None
    playing_running_count: int | FiniteFloat | None = None
    playing_true_count: FiniteFloat | None = None
    betting_running_count: FiniteFloat | None = None
    ace_side_count: AceSideCountResponse | None = None
    ace_adjustment_factor: FiniteFloat | None = None


class PreRoundAnalysisResponse(BaseModel):
    cards_seen: int = Field(ge=0)
    cards_remaining: int = Field(ge=0)
    decks_remaining: FiniteFloat = Field(ge=0)
    bankroll: FiniteFloat
    minimum_bet: FiniteFloat
    policy: BankrollPolicyResponse
    systems: list[PreRoundSystemResult] = Field(min_length=1)
    most_favorable_estimate_system_id: CountSystemId


class MachineEvPreRoundRequest(BaseModel):
    number_of_decks: int = Field(gt=0, strict=True)
    seen_cards: list[CardValue] = Field(default_factory=list)
    bankroll: FiniteFloat | None = None
    minimum_bet: FiniteFloat | None = Field(default=None, gt=0)
    rules: PreRoundRulesPayload | None = None
    engine_mode: Literal[
        "legacy",
        "deterministic",
        "hybrid",
        "monte_carlo",
    ] | None = None
    include_debug_metrics: bool = False
    max_duration_ms: int | None = Field(default=None, gt=0, strict=True)

    @field_validator("seen_cards", mode="before")
    @classmethod
    def normalize_seen_cards(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [str(card).strip().upper() for card in value]


class MachineEvDebugMetricsResponse(BaseModel):
    states_evaluated: int = Field(ge=0)
    duration_ms: FiniteFloat = Field(ge=0)
    cache_hits: int = Field(ge=0)
    cache_misses: int = Field(ge=0)
    timed_out: bool
    warnings: list[str]
    precision_mode: str


class MachineEvPreRoundResponse(BaseModel):
    model_id: Literal["machine_ev"]
    label: Literal["Machine EV"]
    model_type: Literal["composition_ev"]
    is_human_replicable: Literal[False]
    estimated_next_hand_edge: FiniteFloat
    risk_if_minimum_bet: FiniteFloat | None = Field(default=None, ge=0, le=1)
    minimum_bankroll_required_for_minimum_bet: FiniteFloat | None = Field(
        default=None,
        ge=0,
    )
    recommendation_status: str
    recommendation_text: str
    debug_metrics: MachineEvDebugMetricsResponse | None = None
