from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from blackjack_risk_engine.ev import analyze_hand
from blackjack_risk_engine.hand import Hand, parse_card, parse_cards
from blackjack_risk_engine.rules import GameRules


def parse_card_list(value: str) -> list[str]:
    if not value.strip():
        return []

    cards = [item.strip().upper() for item in value.split(",") if item.strip()]
    try:
        parse_cards(cards)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return cards


def parse_card_value(value: str) -> str:
    card = value.strip().upper()
    try:
        parse_card(card)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return card


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blackjack-risk-engine",
        description="Analisa hit vs stand em blackjack usando simulacao Monte Carlo.",
    )
    parser.add_argument(
        "--player",
        required=True,
        type=parse_card_list,
        help="Mao do jogador separada por virgulas. Ex.: 10,6 ou A,7",
    )
    parser.add_argument(
        "--dealer",
        required=True,
        type=parse_card_value,
        help="Carta aberta do dealer. Ex.: 10 ou A",
    )
    parser.add_argument(
        "--seen",
        default=[],
        type=parse_card_list,
        help="Cartas ja vistas adicionais, separadas por virgulas. Ex.: 2,5,6,A,10",
    )
    parser.add_argument(
        "--decks",
        default=6,
        type=int,
        help="Numero de baralhos no shoe. Padrao: 6",
    )
    parser.add_argument(
        "--simulations",
        default=10_000,
        type=int,
        help="Numero de simulacoes Monte Carlo por acao. Padrao: 10000",
    )
    parser.add_argument(
        "--seed",
        default=None,
        type=int,
        help="Seed opcional para resultados reproduziveis.",
    )
    parser.add_argument(
        "--minimum-bet",
        default=10.0,
        type=float,
        help="Aposta minima da mesa para sugestao de aposta. Padrao: 10",
    )
    parser.add_argument(
        "--bankroll",
        default=1000.0,
        type=float,
        help="Banca usada para limitar a sugestao de aposta. Padrao: 1000",
    )
    parser.add_argument(
        "--risk-profile",
        default="moderate",
        choices=("conservative", "moderate", "aggressive"),
        help="Perfil de risco para spread de aposta. Padrao: moderate",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime a analise como JSON serializavel.",
    )
    return parser


def format_rate(value: float) -> str:
    return f"{value:.2%}"


def format_analysis(analysis: dict) -> str:
    ci_low, ci_high = analysis["confidence_interval_95"]
    return (
        f"- {analysis['action']}: "
        f"EV={analysis['ev']:.4f}, "
        f"std_dev={analysis['std_dev']:.4f}, "
        f"standard_error={analysis['standard_error']:.4f}, "
        f"confidence_interval_95=[{ci_low:.4f}, {ci_high:.4f}], "
        f"wins={analysis['wins']}, losses={analysis['losses']}, pushes={analysis['pushes']}, "
        f"win_rate={format_rate(analysis['win_rate'])}, "
        f"lose_rate={format_rate(analysis['lose_rate'])}, "
        f"push_rate={format_rate(analysis['push_rate'])}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        rules = GameRules(number_of_decks=args.decks)
        player_hand = Hand.from_values(args.player)
        dealer_up_card = args.dealer
        analyses = analyze_hand(
            player_hand=player_hand,
            dealer_up_card=dealer_up_card,
            seen_cards=args.seen,
            rules=rules,
            simulations=args.simulations,
            seed=args.seed,
            minimum_bet=args.minimum_bet,
            bankroll=args.bankroll,
            risk_profile=args.risk_profile,
        )
    except ValueError as error:
        parser.error(str(error))

    if args.json:
        print(json.dumps(analyses, ensure_ascii=False, indent=2))
        return 0

    hand_analysis = analyses["hand_analysis"]
    counting = analyses["counting"]
    betting = analyses["betting"]
    recommendation = analyses["recommendation"]
    best = analyses["actions"][0]

    print("blackjack-risk-engine")
    print()
    print("Player hand")
    print(f"- cards: {','.join(hand_analysis['cards'])}")
    print(f"- total: {hand_analysis['total']}")
    print(f"- type: {'soft' if hand_analysis['is_soft'] else 'hard'}")
    print(f"- bust: {hand_analysis['is_bust']}")
    print(f"- natural_blackjack: {hand_analysis['is_blackjack']}")
    print(f"- pair: {hand_analysis['is_pair']}")
    print(f"- can_split: {hand_analysis['can_split']}")
    print()
    print(f"Dealer up card: {dealer_up_card}")
    print(f"Decks: {rules.number_of_decks}")
    print(f"Simulations per action: {args.simulations}")
    print()
    print("Hi-Lo count")
    print(f"- running_count: {counting['running_count']}")
    print(f"- true_count: {counting['true_count']:.4f}")
    print(f"- cards_remaining: {counting['cards_remaining']}")
    print(f"- deck_status: {counting['deck_status']}")
    print()
    print("Bet suggestion")
    print(f"- suggested_bet: {betting['suggested_bet']:.2f}")
    print(f"- bet_units: {betting['bet_units']:.2f}")
    print(f"- risk_profile: {betting['risk_profile']}")
    print(f"- explanation: {betting['explanation']}")
    print()
    print("Action analysis")
    for analysis in analyses["actions"]:
        print(format_analysis(analysis))
    print()
    print("Strategy comparison")
    print(f"- monte_carlo_action: {recommendation['monte_carlo_action']}")
    print(f"- basic_strategy_action: {recommendation['basic_strategy_action']}")
    print(f"- agreement: {recommendation['strategy_agreement']}")
    print(f"- confidence: {recommendation['confidence']:.4f}")
    print(f"- explanation: {recommendation['explanation']}")
    print()
    print(f"Recommended action: {recommendation['best_action']} (EV={best['ev']:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
