from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from blackjack_risk_engine.cards import Card
from blackjack_risk_engine.dealer import DealerDeck, DealerPlayResult, play_dealer_hand_from_initial_hand
from blackjack_risk_engine.decisions import Decision, get_legal_actions
from blackjack_risk_engine.hand import CardInput, Hand, parse_card
from blackjack_risk_engine.rules import GameRules
from blackjack_risk_engine.strategy import choose_continuation_action


@dataclass(frozen=True, slots=True)
class GameState:
    player_hand: Hand
    dealer_up_card: Card
    seen_cards: tuple[Card, ...]
    rules: GameRules


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


@dataclass(frozen=True, slots=True)
class RoundResult:
    player_hand: Hand
    dealer_hand: Hand
    action: Decision
    outcome: float
    dealer_result: DealerPlayResult
    split_hands: tuple[Hand, ...] = ()


def simulate_round(
    player_hand: Hand | Iterable[CardInput],
    dealer_up_card: CardInput,
    deck: DealerDeck,
    rules: GameRules | None = None,
    action: Decision | str = Decision.STAND,
    splits_done: int = 0,
) -> RoundResult:
    """Simulate one simple 1v1 round.

    When the initial action is hit, the player continues with a simplified
    basic-strategy policy that considers total, soft/hard shape, and dealer card.
    Split is currently non-recursive: each split hand uses the same temporary
    hit-until-17 policy, and double after split is not evaluated yet.
    """

    active_rules = rules or GameRules()
    initial_action = _parse_round_action(action)
    player = _copy_hand(player_hand)
    _validate_legal_action(player, active_rules, initial_action, splits_done)

    dealer_up = parse_card(dealer_up_card)
    hole_card = deck.draw()
    dealer_initial_hand = Hand([dealer_up, hole_card])
    initial_dealer_result = DealerPlayResult(
        final_hand=dealer_initial_hand,
        hole_card=hole_card,
        drawn_cards=(),
    )

    if initial_action is Decision.SURRENDER:
        return RoundResult(
            player_hand=player,
            dealer_hand=dealer_initial_hand,
            action=initial_action,
            outcome=-0.5,
            dealer_result=initial_dealer_result,
        )

    natural_blackjack_outcome = _resolve_natural_blackjack(
        player=player,
        dealer=dealer_initial_hand,
        rules=active_rules,
    )
    if natural_blackjack_outcome is not None:
        return RoundResult(
            player_hand=player,
            dealer_hand=dealer_initial_hand,
            action=initial_action,
            outcome=natural_blackjack_outcome,
            dealer_result=initial_dealer_result,
        )

    if initial_action is Decision.HIT:
        _play_strategic_hit_continuation(player, dealer_up, deck)
        if player.is_bust:
            return RoundResult(
                player_hand=player,
                dealer_hand=dealer_initial_hand,
                action=initial_action,
                outcome=-1,
                dealer_result=initial_dealer_result,
            )

    if initial_action is Decision.DOUBLE:
        player.add(deck.draw())
        if player.is_bust:
            return RoundResult(
                player_hand=player,
                dealer_hand=dealer_initial_hand,
                action=initial_action,
                outcome=-2,
                dealer_result=initial_dealer_result,
            )

    if initial_action is Decision.SPLIT:
        split_hands = _create_split_hands(player, deck)
        for split_hand in split_hands:
            _play_until_17_policy(split_hand, deck)

        if all(split_hand.is_bust for split_hand in split_hands):
            return RoundResult(
                player_hand=player,
                dealer_hand=dealer_initial_hand,
                action=initial_action,
                outcome=sum(_compare_hands(split_hand, dealer_initial_hand) for split_hand in split_hands),
                dealer_result=initial_dealer_result,
                split_hands=split_hands,
            )

        dealer_result = play_dealer_hand_from_initial_hand(
            initial_hand=dealer_initial_hand,
            hole_card=hole_card,
            deck=deck,
            rules=active_rules,
        )
        return RoundResult(
            player_hand=player,
            dealer_hand=dealer_result.final_hand,
            action=initial_action,
            outcome=sum(_compare_hands(split_hand, dealer_result.final_hand) for split_hand in split_hands),
            dealer_result=dealer_result,
            split_hands=split_hands,
        )

    dealer_result = play_dealer_hand_from_initial_hand(
        initial_hand=dealer_initial_hand,
        hole_card=hole_card,
        deck=deck,
        rules=active_rules,
    )

    return RoundResult(
        player_hand=player,
        dealer_hand=dealer_result.final_hand,
        action=initial_action,
        outcome=_score_outcome(
            player=player,
            dealer=dealer_result.final_hand,
            multiplier=2 if initial_action is Decision.DOUBLE else 1,
        ),
        dealer_result=dealer_result,
    )


def _parse_round_action(action: Decision | str) -> Decision:
    try:
        parsed_action = action if isinstance(action, Decision) else Decision(action)
    except ValueError as error:
        raise ValueError("action must be one of: hit, stand, double, split, surrender") from error

    if parsed_action not in {
        Decision.HIT,
        Decision.STAND,
        Decision.DOUBLE,
        Decision.SPLIT,
        Decision.SURRENDER,
    }:
        raise ValueError("action must be one of: hit, stand, double, split, surrender")
    return parsed_action


def _validate_legal_action(player: Hand, rules: GameRules, action: Decision, splits_done: int) -> None:
    if action not in get_legal_actions(player, rules, splits_done=splits_done):
        raise ValueError(f"action {action.value} is not legal for this hand and rules")


def _copy_hand(hand: Hand | Iterable[CardInput]) -> Hand:
    if isinstance(hand, Hand):
        return Hand(hand.cards)
    return Hand(hand)


def _resolve_natural_blackjack(player: Hand, dealer: Hand, rules: GameRules) -> float | None:
    if player.is_blackjack and dealer.is_blackjack:
        return 0
    if player.is_blackjack:
        return rules.blackjack_payout_multiplier
    if dealer.is_blackjack:
        return -1
    return None


def _play_strategic_hit_continuation(player: Hand, dealer_up_card: Card, deck: DealerDeck) -> None:
    player.add(deck.draw())
    while choose_continuation_action(player, dealer_up_card) is Decision.HIT:
        player.add(deck.draw())


def _play_until_17_policy(player: Hand, deck: DealerDeck) -> None:
    while not player.is_bust and player.total < 17:
        player.add(deck.draw())


def _create_split_hands(player: Hand, deck: DealerDeck) -> tuple[Hand, Hand]:
    first_card, second_card = player.cards
    first_hand = Hand([first_card, deck.draw()])
    second_hand = Hand([second_card, deck.draw()])
    return first_hand, second_hand


def _compare_hands(player: Hand, dealer: Hand) -> int:
    if player.is_bust:
        return -1
    if dealer.is_bust:
        return 1
    if player.total > dealer.total:
        return 1
    if player.total < dealer.total:
        return -1
    return 0


def _score_outcome(player: Hand, dealer: Hand, multiplier: int = 1) -> int:
    base_outcome = _compare_hands(player, dealer)
    if base_outcome == 0:
        return 0
    return base_outcome * multiplier


class MonteCarloSimulator:
    def __init__(self, config: SimulationConfig | None = None) -> None:
        self.config = config or SimulationConfig()

    def analyze(self, state: GameState) -> SimulationResult:
        from blackjack_risk_engine.ev import analyze_hand

        best_action = analyze_hand(
            player_hand=state.player_hand,
            dealer_up_card=state.dealer_up_card,
            seen_cards=state.seen_cards,
            rules=state.rules,
            simulations=self.config.iterations,
            seed=self.config.seed,
        )
        return SimulationResult(
            best_decision=Decision(best_action["recommendation"]["best_action"]),
            expected_value=best_action["actions"][0]["ev"],
            iterations=best_action["actions"][0]["simulations"],
        )
