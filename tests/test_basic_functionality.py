"""
Test cases for Blackjack AI Agent core functionality.
"""
import pytest
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from game.cards import Card, Rank, Suit, Hand, Shoe
from game.blackjack_env import BlackjackEnvironment, Action
from tools.basic_strategy import BasicStrategy
from tools.card_counting import CardCounter
from tools.money_management import BankrollManager, RiskLevel


class TestCards:
    """Test card and deck functionality"""
    
    def test_card_creation(self):
        """Test card creation and properties"""
        card = Card(Rank.ACE, Suit.SPADES)
        assert card.rank == Rank.ACE
        assert card.suit == Suit.SPADES
        assert card.value == 1  # Ace low value
        assert card.hi_lo_value == -1
    
    def test_card_values(self):
        """Test card value calculations"""
        # Number cards
        two = Card(Rank.TWO, Suit.HEARTS)
        assert two.value == 2
        assert two.hi_lo_value == 1
        
        # Face cards
        king = Card(Rank.KING, Suit.DIAMONDS)
        assert king.value == 10
        assert king.hi_lo_value == -1
        
        # Neutral cards
        seven = Card(Rank.SEVEN, Suit.CLUBS)
        assert seven.value == 7
        assert seven.hi_lo_value == 0
    
    def test_hand_creation(self):
        """Test hand creation and calculations"""
        hand = Hand()
        
        # Add cards
        hand.add_card(Card(Rank.KING, Suit.SPADES))
        hand.add_card(Card(Rank.FIVE, Suit.HEARTS))
        
        assert hand.value == 15
        assert hand.is_hard
        assert not hand.is_soft
        assert not hand.is_pair
    
    def test_soft_hand(self):
        """Test soft hand calculations"""
        hand = Hand()
        hand.add_card(Card(Rank.ACE, Suit.SPADES))
        hand.add_card(Card(Rank.SIX, Suit.HEARTS))
        
        assert hand.value == 17  # A,6 = soft 17
        assert hand.is_soft
        assert not hand.is_hard
    
    def test_blackjack(self):
        """Test blackjack detection"""
        hand = Hand()
        hand.add_card(Card(Rank.ACE, Suit.SPADES))
        hand.add_card(Card(Rank.KING, Suit.HEARTS))
        
        assert hand.value == 21
        assert hand.is_blackjack
        assert hand.is_soft
    
    def test_pair_detection(self):
        """Test pair detection"""
        hand = Hand()
        hand.add_card(Card(Rank.EIGHT, Suit.SPADES))
        hand.add_card(Card(Rank.EIGHT, Suit.HEARTS))
        
        assert hand.is_pair
        assert hand.can_split
        assert hand.value == 16
    
    def test_shoe_creation(self):
        """Test shoe creation and shuffling"""
        shoe = Shoe(num_decks=6, penetration=0.75)
        
        assert shoe.num_decks == 6
        assert shoe.cards_remaining == 6 * 52
        assert shoe.decks_remaining == 6.0
        assert shoe.running_count == 0


class TestBasicStrategy:
    """Test basic strategy functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.strategy = BasicStrategy()
    
    def test_hard_hand_recommendation(self):
        """Test hard hand recommendations"""
        # Create a hard 16
        hand = Hand()
        hand.add_card(Card(Rank.TEN, Suit.SPADES))
        hand.add_card(Card(Rank.SIX, Suit.HEARTS))
        
        dealer_upcard = Card(Rank.SEVEN, Suit.DIAMONDS)
        available_actions = [Action.HIT, Action.STAND]
        
        action, explanation, confidence = self.strategy.get_recommendation(
            hand, dealer_upcard, available_actions
        )
        
        assert action in available_actions
        assert isinstance(explanation, str)
        assert 0 <= confidence <= 1
    
    def test_soft_hand_recommendation(self):
        """Test soft hand recommendations"""
        # Create soft 18 (A,7)
        hand = Hand()
        hand.add_card(Card(Rank.ACE, Suit.SPADES))
        hand.add_card(Card(Rank.SEVEN, Suit.HEARTS))
        
        dealer_upcard = Card(Rank.NINE, Suit.DIAMONDS)
        available_actions = [Action.HIT, Action.STAND, Action.DOUBLE]
        
        action, explanation, confidence = self.strategy.get_recommendation(
            hand, dealer_upcard, available_actions
        )
        
        assert action in available_actions
        assert hand.is_soft
    
    def test_pair_recommendation(self):
        """Test pair splitting recommendations"""
        # Create pair of 8s
        hand = Hand()
        hand.add_card(Card(Rank.EIGHT, Suit.SPADES))
        hand.add_card(Card(Rank.EIGHT, Suit.HEARTS))
        
        dealer_upcard = Card(Rank.TEN, Suit.DIAMONDS)
        available_actions = [Action.HIT, Action.STAND, Action.SPLIT]
        
        action, explanation, confidence = self.strategy.get_recommendation(
            hand, dealer_upcard, available_actions
        )
        
        # Pair of 8s should always split
        assert action == Action.SPLIT
        assert hand.is_pair


class TestCardCounting:
    """Test card counting functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.counter = CardCounter()
    
    def test_hi_lo_counting(self):
        """Test Hi-Lo count updates"""
        # Low cards (+1)
        low_card = Card(Rank.FIVE, Suit.SPADES)
        count_value = self.counter.update_count(low_card)
        assert count_value == 1
        assert self.counter.running_count == 1
        
        # High card (-1)
        high_card = Card(Rank.KING, Suit.HEARTS)
        count_value = self.counter.update_count(high_card)
        assert count_value == -1
        assert self.counter.running_count == 0
        
        # Neutral card (0)
        neutral_card = Card(Rank.EIGHT, Suit.DIAMONDS)
        count_value = self.counter.update_count(neutral_card)
        assert count_value == 0
        assert self.counter.running_count == 0
    
    def test_true_count_calculation(self):
        """Test true count calculation"""
        self.counter.running_count = 6
        true_count = self.counter.get_true_count(3.0)  # 3 decks remaining
        assert true_count == 2.0
    
    def test_betting_recommendation(self):
        """Test betting size recommendations"""
        bet_amount, explanation = self.counter.get_betting_recommendation(
            true_count=3.0,
            base_bet=25.0,
            bankroll=5000.0
        )
        
        assert bet_amount > 25.0  # Should increase bet on positive count
        assert isinstance(explanation, str)
        assert "TC 3.0" in explanation


class TestBankrollManager:
    """Test bankroll management functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = BankrollManager(
            initial_bankroll=10000,
            base_bet=25,
            risk_level=RiskLevel.MODERATE
        )
    
    def test_bankroll_initialization(self):
        """Test bankroll manager initialization"""
        assert self.manager.initial_bankroll == 10000
        assert self.manager.current_bankroll == 10000
        assert self.manager.base_bet == 25
        assert self.manager.risk_level == RiskLevel.MODERATE
    
    def test_kelly_bet_calculation(self):
        """Test Kelly criterion bet calculation"""
        kelly_bet = self.manager.calculate_kelly_bet(
            win_probability=0.55,
            win_amount=1.0,
            loss_amount=1.0
        )
        
        assert kelly_bet > 0
        assert kelly_bet < self.manager.current_bankroll
    
    def test_count_based_betting(self):
        """Test count-based bet recommendations"""
        # Positive count should increase bet
        bet_rec = self.manager.get_count_based_bet(true_count=3.0)
        assert bet_rec.bet_amount > self.manager.base_bet
        assert bet_rec.bet_multiplier > 1.0
        
        # Negative count should use minimum bet
        bet_rec = self.manager.get_count_based_bet(true_count=-2.0)
        assert bet_rec.bet_amount == self.manager.base_bet
        assert bet_rec.bet_multiplier == 1.0
    
    def test_bankroll_update(self):
        """Test bankroll updates after hands"""
        initial_bankroll = self.manager.current_bankroll
        
        # Win
        self.manager.update_bankroll(result=50, bet_amount=25)
        assert self.manager.current_bankroll == initial_bankroll + 50
        
        # Loss
        self.manager.update_bankroll(result=-25, bet_amount=25)
        assert self.manager.current_bankroll == initial_bankroll + 25
    
    def test_stop_loss_check(self):
        """Test stop-loss functionality"""
        # Simulate large losses
        self.manager.current_bankroll = 3000  # 70% loss
        
        should_stop, reason = self.manager.should_stop_session()
        assert should_stop
        assert "stop-loss" in reason.lower()


class TestBlackjackEnvironment:
    """Test game environment functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.env = BlackjackEnvironment()
    
    def test_environment_initialization(self):
        """Test environment setup"""
        assert self.env.shoe is not None
        assert self.env.game_state is not None
        assert self.env.config is not None
    
    def test_new_round_start(self):
        """Test starting a new round"""
        game_state = self.env.start_new_round(bet_amount=25)
        
        assert len(game_state.player_hands) == 1
        assert len(game_state.player_hands[0].cards) == 2
        assert len(game_state.dealer_hand.cards) == 2
        assert game_state.player_hands[0].bet == 25
    
    def test_valid_actions(self):
        """Test valid action determination"""
        self.env.start_new_round(bet_amount=25)
        valid_actions = self.env.get_valid_actions()
        
        assert Action.HIT in valid_actions
        assert Action.STAND in valid_actions
        # Other actions depend on hand composition
    
    def test_action_execution(self):
        """Test action execution"""
        self.env.start_new_round(bet_amount=25)
        initial_cards = len(self.env.game_state.player_hands[0].cards)
        
        # Hit action should add a card
        self.env.take_action(Action.HIT)
        final_cards = len(self.env.game_state.player_hands[0].cards)
        
        # Either added a card or moved to next hand (if 21/bust)
        assert final_cards >= initial_cards


def run_basic_tests():
    """Run basic functionality tests"""
    print("Running basic tests...")
    
    # Test card creation
    try:
        card = Card(Rank.ACE, Suit.SPADES)
        print("✓ Card creation works")
    except Exception as e:
        print(f"✗ Card creation failed: {e}")
        return False
    
    # Test hand calculation
    try:
        hand = Hand()
        hand.add_card(Card(Rank.KING, Suit.SPADES))
        hand.add_card(Card(Rank.ACE, Suit.HEARTS))
        assert hand.value == 21
        assert hand.is_blackjack
        print("✓ Hand calculation works")
    except Exception as e:
        print(f"✗ Hand calculation failed: {e}")
        return False
    
    # Test basic strategy
    try:
        strategy = BasicStrategy()
        hand = Hand()
        hand.add_card(Card(Rank.TEN, Suit.SPADES))
        hand.add_card(Card(Rank.SIX, Suit.HEARTS))
        
        dealer_upcard = Card(Rank.TEN, Suit.DIAMONDS)
        action, explanation, confidence = strategy.get_recommendation(
            hand, dealer_upcard, [Action.HIT, Action.STAND]
        )
        print("✓ Basic strategy works")
    except Exception as e:
        print(f"✗ Basic strategy failed: {e}")
        return False
    
    # Test card counting
    try:
        counter = CardCounter()
        counter.update_count(Card(Rank.FIVE, Suit.SPADES))  # +1
        counter.update_count(Card(Rank.KING, Suit.HEARTS))  # -1
        assert counter.running_count == 0
        print("✓ Card counting works")
    except Exception as e:
        print(f"✗ Card counting failed: {e}")
        return False
    
    # Test bankroll management
    try:
        manager = BankrollManager(10000, 25)
        bet_rec = manager.get_count_based_bet(2.0)
        assert bet_rec.bet_amount >= 25
        print("✓ Bankroll management works")
    except Exception as e:
        print(f"✗ Bankroll management failed: {e}")
        return False
    
    # Test environment
    try:
        env = BlackjackEnvironment()
        env.start_new_round(25)
        actions = env.get_valid_actions()
        assert len(actions) > 0
        print("✓ Game environment works")
    except Exception as e:
        print(f"✗ Game environment failed: {e}")
        return False
    
    print("\n✅ All basic tests passed!")
    return True


if __name__ == "__main__":
    run_basic_tests()
