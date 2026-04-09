"""
Blackjack game environment implementation.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import yaml
import random

from .cards import Shoe, Hand, Card


class Action(Enum):
    """Possible player actions in Blackjack"""
    HIT = "hit"
    STAND = "stand"
    DOUBLE = "double"
    SPLIT = "split"
    SURRENDER = "surrender"


class GameResult(Enum):
    """Game result from player's perspective"""
    WIN = "win"
    LOSE = "lose"
    PUSH = "push"
    BLACKJACK = "blackjack"
    SURRENDER = "surrender"


@dataclass
class GameState:
    """Represents the current state of a Blackjack game"""
    player_hands: List[Hand] = field(default_factory=list)
    dealer_hand: Hand = field(default_factory=Hand)
    current_hand_index: int = 0
    shoe: Optional[Shoe] = None
    round_number: int = 0
    bankroll: float = 10000.0
    
    @property
    def current_hand(self) -> Optional[Hand]:
        """Get the current active player hand"""
        if 0 <= self.current_hand_index < len(self.player_hands):
            return self.player_hands[self.current_hand_index]
        return None
    
    @property
    def is_game_over(self) -> bool:
        """Check if current round is complete"""
        return self.current_hand_index >= len(self.player_hands)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert game state to dictionary for logging"""
        return {
            'round_number': self.round_number,
            'player_hands': [
                {
                    'cards': [str(card) for card in hand.cards],
                    'value': hand.value,
                    'bet': hand.bet,
                    'is_busted': hand.is_busted,
                    'is_blackjack': hand.is_blackjack,
                    'is_doubled': hand.is_doubled,
                    'is_surrendered': hand.is_surrendered
                }
                for hand in self.player_hands
            ],
            'dealer_hand': {
                'cards': [str(card) for card in self.dealer_hand.cards],
                'value': self.dealer_hand.value,
                'is_busted': self.dealer_hand.is_busted
            },
            'shoe_info': {
                'running_count': self.shoe.running_count if self.shoe else 0,
                'true_count': self.shoe.true_count if self.shoe else 0,
                'cards_remaining': self.shoe.cards_remaining if self.shoe else 0,
                'decks_remaining': self.shoe.decks_remaining if self.shoe else 0
            },
            'bankroll': self.bankroll
        }


class BlackjackEnvironment:
    """Blackjack game environment with configurable rules"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.shoe = Shoe(
            num_decks=self.config['game']['num_decks'],
            penetration=self.config['game']['penetration']
        )
        self.game_state = GameState(shoe=self.shoe)
        self._setup_initial_bankroll()
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if config_path is None:
            config_path = "config/config.yaml"
        
        try:
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            # Return default configuration
            return {
                'game': {
                    'num_decks': 6,
                    'penetration': 0.75,
                    'dealer_hits_soft_17': False,
                    'blackjack_pays': 1.5,
                    'double_after_split': True,
                    'double_on_any_two': True,
                    'surrender_allowed': True,
                    'insurance_allowed': False,
                    'max_splits': 3,
                    'split_aces_get_one_card': True
                },
                'bankroll': {
                    'initial_bankroll': 10000,
                    'base_bet': 25
                }
            }
    
    def _setup_initial_bankroll(self):
        """Setup initial bankroll"""
        self.game_state.bankroll = self.config['bankroll']['initial_bankroll']
    
    def start_new_round(self, bet_amount: Optional[float] = None) -> GameState:
        """Start a new round of Blackjack"""
        # Check if shoe needs shuffle
        if self.shoe.needs_shuffle():
            self.shoe.reset()
        
        # Setup bet
        if bet_amount is None:
            bet_amount = self.config['bankroll']['base_bet']
        
        if bet_amount > self.game_state.bankroll:
            raise ValueError(f"Insufficient bankroll: {self.game_state.bankroll}")
        
        # Initialize new round
        self.game_state.player_hands = [Hand()]
        self.game_state.dealer_hand = Hand()
        self.game_state.current_hand_index = 0
        self.game_state.round_number += 1
        
        # Set bet
        self.game_state.player_hands[0].bet = bet_amount
        
        # Deal initial cards
        self._deal_initial_cards()
        
        return self.game_state
    
    def _deal_initial_cards(self):
        """Deal initial two cards to player and dealer"""
        # Player first card
        card = self.shoe.deal_card()
        if card:
            self.game_state.player_hands[0].add_card(card)
        
        # Dealer first card (face up)
        card = self.shoe.deal_card()
        if card:
            self.game_state.dealer_hand.add_card(card)
        
        # Player second card
        card = self.shoe.deal_card()
        if card:
            self.game_state.player_hands[0].add_card(card)
        
        # Dealer second card (hole card)
        card = self.shoe.deal_card()
        if card:
            self.game_state.dealer_hand.add_card(card)
    
    def get_valid_actions(self, hand_index: Optional[int] = None) -> List[Action]:
        """Get list of valid actions for current hand"""
        if hand_index is None:
            hand_index = self.game_state.current_hand_index
        
        if hand_index >= len(self.game_state.player_hands):
            return []
        
        hand = self.game_state.player_hands[hand_index]
        valid_actions = []
        
        # If hand is blackjack or busted, no actions available (should be automatically handled)
        if hand.is_blackjack or hand.is_busted:
            return []
        
        # Always can hit or stand for active hands
        valid_actions.extend([Action.HIT, Action.STAND])
        
        # Double down conditions
        if (hand.can_double and 
            self.config['game']['double_on_any_two'] and
            self.game_state.bankroll >= hand.bet):
            valid_actions.append(Action.DOUBLE)
        
        # Split conditions
        if (hand.can_split and 
            len(self.game_state.player_hands) < self.config['game'].get('max_splits', 4) and
            self.game_state.bankroll >= hand.bet):
            valid_actions.append(Action.SPLIT)
        
        # Surrender conditions (early surrender only)
        if (len(hand.cards) == 2 and 
            not hand.is_split and
            self.config['game']['surrender_allowed']):
            valid_actions.append(Action.SURRENDER)
        
        return valid_actions
    
    def take_action(self, action: Action, hand_index: Optional[int] = None) -> GameState:
        """Execute an action for the current hand"""
        if hand_index is None:
            hand_index = self.game_state.current_hand_index
        
        if hand_index >= len(self.game_state.player_hands):
            raise ValueError(f"Invalid hand index: {hand_index}")
        
        hand = self.game_state.player_hands[hand_index]
        
        if action not in self.get_valid_actions(hand_index):
            raise ValueError(f"Invalid action: {action} for hand {hand_index}")
        
        if action == Action.HIT:
            self._hit(hand)
        elif action == Action.STAND:
            self._stand()
        elif action == Action.DOUBLE:
            self._double_down(hand)
        elif action == Action.SPLIT:
            self._split(hand_index)
        elif action == Action.SURRENDER:
            self._surrender(hand)
        
        return self.game_state
    
    def _hit(self, hand: Hand):
        """Deal one card to the hand"""
        card = self.shoe.deal_card()
        if card:
            hand.add_card(card)
        
        # If busted or 21, move to next hand
        if hand.is_busted or hand.value == 21:
            self._move_to_next_hand()
    
    def _stand(self):
        """Stand on current hand"""
        self._move_to_next_hand()
    
    def _double_down(self, hand: Hand):
        """Double down on current hand"""
        # Deduct additional bet from bankroll
        self.game_state.bankroll -= hand.bet
        hand.double_down()
        
        # Deal exactly one more card
        card = self.shoe.deal_card()
        if card:
            hand.add_card(card)
        
        # Automatically move to next hand
        self._move_to_next_hand()
    
    def _split(self, hand_index: int):
        """Split the current hand"""
        hand = self.game_state.player_hands[hand_index]
        
        # Deduct split bet from bankroll
        self.game_state.bankroll -= hand.bet
        
        # Create new hand from split
        new_hand = hand.split()
        
        # Insert new hand after current hand
        self.game_state.player_hands.insert(hand_index + 1, new_hand)
        
        # Deal one card to each split hand
        for split_hand in [hand, new_hand]:
            card = self.shoe.deal_card()
            if card:
                split_hand.add_card(card)
        
        # Special rule: splitting aces gets only one card each
        if (hand.cards[0].rank.value == 'A' and 
            self.config['game']['split_aces_get_one_card']):
            # Move to next hand immediately
            self.game_state.current_hand_index += 1
    
    def _surrender(self, hand: Hand):
        """Surrender the current hand"""
        hand.surrender()
        self._move_to_next_hand()
    
    def _move_to_next_hand(self):
        """Move to the next player hand"""
        self.game_state.current_hand_index += 1
        
        # Skip over any hands that are blackjack or busted (auto-resolved)
        while (self.game_state.current_hand_index < len(self.game_state.player_hands)):
            current_hand = self.game_state.player_hands[self.game_state.current_hand_index]
            if not current_hand.is_blackjack and not current_hand.is_busted:
                break
            self.game_state.current_hand_index += 1
    
    def play_dealer(self) -> GameState:
        """Play the dealer's hand according to house rules"""
        if self.game_state.is_game_over:
            # Check if any player hands are still active (not busted/surrendered)
            active_hands = [
                hand for hand in self.game_state.player_hands 
                if not hand.is_busted and not hand.is_surrendered
            ]
            
            if active_hands:  # Only play dealer if player has active hands
                dealer_hand = self.game_state.dealer_hand
                
                # Dealer hits on soft 17 if configured
                should_hit_soft_17 = self.config['game']['dealer_hits_soft_17']
                
                while (dealer_hand.value < 17 or 
                       (dealer_hand.value == 17 and dealer_hand.is_soft and should_hit_soft_17)):
                    card = self.shoe.deal_card()
                    if card:
                        dealer_hand.add_card(card)
                    else:
                        break  # No more cards in shoe
        
        return self.game_state
    
    def calculate_results(self) -> List[Tuple[GameResult, float]]:
        """Calculate results for all hands and return (result, payout) pairs"""
        if not self.game_state.is_game_over:
            raise ValueError("Cannot calculate results before round is complete")
        
        results = []
        dealer_value = self.game_state.dealer_hand.value
        dealer_busted = self.game_state.dealer_hand.is_busted
        dealer_blackjack = self.game_state.dealer_hand.is_blackjack
        
        for hand in self.game_state.player_hands:
            result, payout = self._calculate_hand_result(
                hand, dealer_value, dealer_busted, dealer_blackjack
            )
            results.append((result, payout))
            
            # Update bankroll
            self.game_state.bankroll += payout
        
        return results
    
    def _calculate_hand_result(
        self, 
        hand: Hand, 
        dealer_value: int, 
        dealer_busted: bool, 
        dealer_blackjack: bool
    ) -> Tuple[GameResult, float]:
        """Calculate result and payout for a single hand"""
        bet = hand.bet
        
        # Surrender
        if hand.is_surrendered:
            return GameResult.SURRENDER, bet * 0.5
        
        # Player busted
        if hand.is_busted:
            return GameResult.LOSE, 0.0
        
        # Player blackjack
        if hand.is_blackjack:
            if dealer_blackjack:
                return GameResult.PUSH, bet  # Push
            else:
                blackjack_payout = bet * (1 + self.config['game']['blackjack_pays'])
                return GameResult.BLACKJACK, blackjack_payout
        
        # Dealer blackjack (player doesn't have blackjack)
        if dealer_blackjack:
            return GameResult.LOSE, 0.0
        
        # Dealer busted
        if dealer_busted:
            return GameResult.WIN, bet * 2
        
        # Compare values
        player_value = hand.value
        
        if player_value > dealer_value:
            return GameResult.WIN, bet * 2
        elif player_value < dealer_value:
            return GameResult.LOSE, 0.0
        else:
            return GameResult.PUSH, bet  # Push
    
    def get_hand_description(self, hand_index: int = 0) -> str:
        """Get a text description of a hand for the AI agent"""
        if hand_index >= len(self.game_state.player_hands):
            return "Invalid hand index"
        
        hand = self.game_state.player_hands[hand_index]
        description = f"Player hand {hand_index + 1}: {hand}"
        
        if hand.is_pair:
            description += " (pair)"
        if hand.can_split:
            description += " (can split)"
        if hand.can_double:
            description += " (can double)"
        
        return description
    
    def get_dealer_upcard(self) -> Optional[Card]:
        """Get dealer's face-up card"""
        if self.game_state.dealer_hand.cards:
            return self.game_state.dealer_hand.cards[0]
        return None
    
    def get_game_summary(self) -> str:
        """Get a summary of the current game state"""
        summary = f"Round {self.game_state.round_number}\n"
        summary += f"Bankroll: ${self.game_state.bankroll:.2f}\n"
        
        if self.shoe:
            summary += f"Running Count: {self.shoe.running_count}\n"
            summary += f"True Count: {self.shoe.true_count:.2f}\n"
            summary += f"Decks Remaining: {self.shoe.decks_remaining:.1f}\n"
        
        # Player hands
        for i, hand in enumerate(self.game_state.player_hands):
            current_marker = " (current)" if i == self.game_state.current_hand_index else ""
            summary += f"Player hand {i + 1}: {hand} [Bet: ${hand.bet}]{current_marker}\n"
        
        # Dealer hand
        if len(self.game_state.dealer_hand.cards) > 0:
            if self.game_state.is_game_over:
                summary += f"Dealer: {self.game_state.dealer_hand}\n"
            else:
                # Show only upcard during play
                upcard = self.game_state.dealer_hand.cards[0]
                summary += f"Dealer: {upcard} [?]\n"
        
        return summary
