"""
Blackjack game cards and deck implementation.
"""
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
import random


class Suit(Enum):
    """Card suits"""
    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"
    SPADES = "♠"


class Rank(Enum):
    """Card ranks"""
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


@dataclass
class Card:
    """Represents a playing card"""
    rank: Rank
    suit: Suit
    
    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.value}"
    
    def __repr__(self) -> str:
        return f"Card({self.rank.value}, {self.suit.value})"
    
    @property
    def value(self) -> int:
        """Returns the blackjack value of the card (Ace = 1, Face cards = 10)"""
        if self.rank in [Rank.JACK, Rank.QUEEN, Rank.KING]:
            return 10
        elif self.rank == Rank.ACE:
            return 1  # Ace 按 1 计算，具体值在 Hand 中处理
        else:
            return int(self.rank.value)
    
    @property
    def hi_lo_value(self) -> int:
        """Returns Hi-Lo counting system value"""
        if self.rank in [Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX]:
            return 1
        elif self.rank in [Rank.SEVEN, Rank.EIGHT, Rank.NINE]:
            return 0
        else:  # 10, J, Q, K, A
            return -1


class Shoe:
    """Multi-deck shoe for Blackjack"""
    
    def __init__(self, num_decks: int = 6, penetration: float = 0.75):
        self.num_decks = num_decks
        self.penetration = penetration
        self.cards: List[Card] = []
        self.cut_card_position = 0
        self.running_count = 0
        self._build_shoe()
        self.shuffle()
    
    def _build_shoe(self):
        """Build the shoe with specified number of decks"""
        self.cards = []
        for _ in range(self.num_decks):
            for suit in Suit:
                for rank in Rank:
                    self.cards.append(Card(rank, suit))
    
    def shuffle(self):
        """Shuffle the shoe and set cut card position"""
        random.shuffle(self.cards)
        total_cards = len(self.cards)
        self.cut_card_position = int(total_cards * self.penetration)
        self.running_count = 0
    
    def deal_card(self) -> Optional[Card]:
        """Deal one card from the shoe"""
        if self.needs_shuffle():
            return None
        
        if not self.cards:
            return None
            
        card = self.cards.pop()
        self.running_count += card.hi_lo_value
        return card
    
    def needs_shuffle(self) -> bool:
        """Check if shoe needs to be reshuffled"""
        return len(self.cards) <= (self.num_decks * 52 - self.cut_card_position)
    
    @property
    def cards_remaining(self) -> int:
        """Number of cards remaining in shoe"""
        return len(self.cards)
    
    @property
    def decks_remaining(self) -> float:
        """Approximate number of decks remaining"""
        return self.cards_remaining / 52.0
    
    @property
    def true_count(self) -> float:
        """Calculate true count for card counting"""
        if self.decks_remaining <= 0:
            return 0.0
        return self.running_count / self.decks_remaining
    
    def reset(self):
        """Reset and rebuild the shoe"""
        self._build_shoe()
        self.shuffle()


class Hand:
    """Represents a Blackjack hand"""
    
    def __init__(self):
        self.cards: List[Card] = []
        self.bet: float = 0.0
        self.is_doubled: bool = False
        self.is_surrendered: bool = False
        self.is_split: bool = False
        self.is_blackjack: bool = False
    
    def add_card(self, card: Card):
        """Add a card to the hand"""
        self.cards.append(card)
        
        # Check for blackjack (21 with first two cards)
        if len(self.cards) == 2 and self.value == 21:
            self.is_blackjack = True
    
    @property
    def value(self) -> int:
        """Calculate the best value of the hand"""
        total = sum(card.value for card in self.cards)
        num_aces = sum(1 for card in self.cards if card.rank == Rank.ACE)
        
        # Adjust for aces (count as 11 if possible)
        while num_aces > 0 and total + 10 <= 21:
            total += 10
            num_aces -= 1
        
        return total
    
    @property
    def is_soft(self) -> bool:
        """Check if hand is soft (contains ace counted as 11)"""
        total = sum(card.value for card in self.cards)
        num_aces = sum(1 for card in self.cards if card.rank == Rank.ACE)
        
        # If we have aces and can count one as 11 without busting
        return num_aces > 0 and total + 10 <= 21 and total + 10 == self.value
    
    @property
    def is_hard(self) -> bool:
        """Check if hand is hard (no aces counted as 11)"""
        return not self.is_soft
    
    @property
    def is_pair(self) -> bool:
        """Check if hand is a pair (for splitting)"""
        if len(self.cards) != 2:
            return False
        
        # Check if both cards have same value (10, J, Q, K all count as 10)
        return self.cards[0].value == self.cards[1].value or (
            self.cards[0].value >= 10 and self.cards[1].value >= 10
        )
    
    @property
    def is_busted(self) -> bool:
        """Check if hand is busted (over 21)"""
        return self.value > 21
    
    @property
    def can_split(self) -> bool:
        """Check if hand can be split"""
        return len(self.cards) == 2 and self.is_pair and not self.is_split
    
    @property
    def can_double(self) -> bool:
        """Check if hand can be doubled"""
        return len(self.cards) == 2 and not self.is_doubled and not self.is_split
    
    def split(self) -> 'Hand':
        """Split the hand and return the new hand"""
        if not self.can_split:
            raise ValueError("Hand cannot be split")
        
        # Create new hand with second card
        new_hand = Hand()
        new_hand.add_card(self.cards.pop())
        new_hand.bet = self.bet
        new_hand.is_split = True
        
        self.is_split = True
        return new_hand
    
    def double_down(self):
        """Double the bet"""
        if not self.can_double:
            raise ValueError("Hand cannot be doubled")
        
        self.bet *= 2
        self.is_doubled = True
    
    def surrender(self):
        """Surrender the hand"""
        if len(self.cards) != 2:
            raise ValueError("Can only surrender with first two cards")
        
        self.is_surrendered = True
    
    def __str__(self) -> str:
        cards_str = " ".join(str(card) for card in self.cards)
        value_str = f"[{self.value}]"
        if self.is_soft:
            value_str += "(soft)"
        if self.is_blackjack:
            value_str += "(BJ)"
        return f"{cards_str} {value_str}"
    
    def __repr__(self) -> str:
        return f"Hand({[str(card) for card in self.cards]}, value={self.value})"
