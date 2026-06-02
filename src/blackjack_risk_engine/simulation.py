from __future__ import annotations

from dataclasses import dataclass

from blackjack_risk_engine.cards import Card
from blackjack_risk_engine.decisions import Decision
from blackjack_risk_engine.hand import Hand
from blackjack_risk_engine.rules import TableRules


@dataclass(frozen=True, slots=True)
class GameState:
    player_hand: Hand
    dealer_up_card: Card
    seen_cards: tuple[Card, ...]
    rules: TableRules


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    iterations: int = 10_000
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.iterations <= 0:
            raise ValueError("iterations must be greater than zero")


@dataclass(frozen=True, slots=True)
class SimulationResult:
    best_decision: Decision
    expected_value: float
    iterations: int


class MonteCarloSimulator:
    def __init__(self, config: SimulationConfig | None = None) -> None:
        self.config = config or SimulationConfig()

    def analyze(self, state: GameState) -> SimulationResult:
        raise NotImplementedError("Monte Carlo decision analysis is not implemented yet")
