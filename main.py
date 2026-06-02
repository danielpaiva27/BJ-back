from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from blackjack_risk_engine.cards import Card, Rank, Suit
from blackjack_risk_engine.counting import running_count
from blackjack_risk_engine.dealer import DealerPolicy
from blackjack_risk_engine.hand import Hand
from blackjack_risk_engine.rules import TableRules


def main() -> None:
    rules = TableRules()
    player_hand = Hand(
        cards=[
            Card(Rank.ACE, Suit.SPADES),
            Card(Rank.SIX, Suit.HEARTS),
        ]
    )
    dealer_up_card = Card(Rank.TEN, Suit.CLUBS)
    seen_cards = [*player_hand.cards, dealer_up_card]

    print("blackjack-risk-engine")
    print(f"Player hand: {player_hand} -> value={player_hand.best_value}")
    print(f"Dealer up card: {dealer_up_card}")
    print(f"Dealer hits soft 17: {rules.dealer_hits_soft_17}")
    print(f"Dealer should hit player hand shape? {DealerPolicy(rules).should_hit(player_hand)}")
    print(f"Hi-Lo running count for seen cards: {running_count(seen_cards)}")


if __name__ == "__main__":
    main()
