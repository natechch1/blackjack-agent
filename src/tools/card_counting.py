"""
Card counting tools for Blackjack AI Agent.
Implements Hi-Lo system and true count calculations.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from ..game.cards import Card, Rank, Shoe


@dataclass
class CountInfo:
    """Information about current count state"""
    running_count: int
    true_count: float
    cards_seen: int
    decks_remaining: float
    betting_correlation: float
    playing_efficiency: float


class CardCounter:
    """Hi-Lo card counting system implementation"""
    
    def __init__(self):
        self.running_count = 0
        self.cards_seen = 0
        self.initial_decks = 6
        
        # Hi-Lo values
        self.hi_lo_values = {
            Rank.TWO: 1, Rank.THREE: 1, Rank.FOUR: 1, Rank.FIVE: 1, Rank.SIX: 1,
            Rank.SEVEN: 0, Rank.EIGHT: 0, Rank.NINE: 0,
            Rank.TEN: -1, Rank.JACK: -1, Rank.QUEEN: -1, Rank.KING: -1, Rank.ACE: -1
        }
    
    def update_count(self, card: Card) -> int:
        """Update running count with new card"""
        count_value = self.hi_lo_values[card.rank]
        self.running_count += count_value
        self.cards_seen += 1
        return count_value
    
    def get_true_count(self, decks_remaining: float) -> float:
        """Calculate true count"""
        if decks_remaining <= 0:
            return 0.0
        return self.running_count / decks_remaining
    
    def get_count_info(self, shoe: Shoe) -> CountInfo:
        """Get comprehensive count information"""
        true_count = self.get_true_count(shoe.decks_remaining)
        
        return CountInfo(
            running_count=self.running_count,
            true_count=true_count,
            cards_seen=self.cards_seen,
            decks_remaining=shoe.decks_remaining,
            betting_correlation=0.97,  # Hi-Lo betting correlation
            playing_efficiency=0.51   # Hi-Lo playing efficiency
        )
    
    def reset_count(self, num_decks: int = 6):
        """Reset count for new shoe"""
        self.running_count = 0
        self.cards_seen = 0
        self.initial_decks = num_decks
    
    def get_betting_recommendation(
        self, 
        true_count: float, 
        base_bet: float, 
        bankroll: float,
        kelly_fraction: float = 0.25,
        max_bet_multiplier: int = 8
    ) -> Tuple[float, str]:
        """
        Calculate recommended bet size based on true count
        Uses Kelly Criterion with conservative fraction
        """
        
        # Basic bet sizing based on true count
        if true_count <= 1:
            bet_multiplier = 1  # Minimum bet
            explanation = f"TC {true_count:.1f}: Minimum bet (no advantage)"
        elif true_count <= 2:
            bet_multiplier = 2
            explanation = f"TC {true_count:.1f}: 2x base bet (small advantage)"
        elif true_count <= 3:
            bet_multiplier = 3
            explanation = f"TC {true_count:.1f}: 3x base bet (moderate advantage)"
        elif true_count <= 4:
            bet_multiplier = 5
            explanation = f"TC {true_count:.1f}: 5x base bet (good advantage)"
        else:
            bet_multiplier = min(max_bet_multiplier, int(true_count))
            explanation = f"TC {true_count:.1f}: {bet_multiplier}x base bet (strong advantage)"
        
        # Apply Kelly fraction for conservative betting
        recommended_bet = base_bet * bet_multiplier * kelly_fraction
        
        # Ensure bet doesn't exceed bankroll limits
        max_allowed_bet = bankroll * 0.05  # Never bet more than 5% of bankroll
        recommended_bet = min(recommended_bet, max_allowed_bet)
        
        # Round to nearest $5
        recommended_bet = round(recommended_bet / 5) * 5
        recommended_bet = max(recommended_bet, base_bet)  # Never bet less than base
        
        explanation += f" | Kelly-adjusted: ${recommended_bet:.0f}"
        
        return recommended_bet, explanation
    
    def should_take_insurance(self, true_count: float) -> Tuple[bool, str]:
        """Determine if insurance bet is profitable"""
        # Insurance is profitable when true count >= +3 in Hi-Lo
        if true_count >= 3:
            return True, f"Take insurance at TC {true_count:.1f} (profitable)"
        else:
            return False, f"Skip insurance at TC {true_count:.1f} (not profitable)"
    
    def get_risk_assessment(self, true_count: float, bankroll: float) -> str:
        """Provide risk assessment based on count and bankroll"""
        if true_count >= 4:
            return "HIGH ADVANTAGE - Aggressive play recommended"
        elif true_count >= 2:
            return "MODERATE ADVANTAGE - Increase bets"
        elif true_count >= 0:
            return "SLIGHT ADVANTAGE - Play basic strategy"
        elif true_count >= -2:
            return "SLIGHT DISADVANTAGE - Reduce bets"
        else:
            return "HIGH DISADVANTAGE - Consider leaving table"


class CountingAnalyzer:
    """Analyzes counting system effectiveness"""
    
    def __init__(self):
        self.hand_history = []
        self.count_accuracy = []
    
    def analyze_session(
        self, 
        game_log: List[Dict], 
        counter: CardCounter
    ) -> Dict[str, float]:
        """Analyze counting performance over a session"""
        
        total_hands = len(game_log)
        profitable_counts = sum(1 for hand in game_log if hand.get('true_count', 0) > 1)
        
        # Calculate average advantage
        avg_true_count = sum(hand.get('true_count', 0) for hand in game_log) / max(total_hands, 1)
        
        # Calculate betting correlation
        correct_bet_increases = sum(
            1 for hand in game_log 
            if hand.get('true_count', 0) > 1 and hand.get('bet_multiplier', 1) > 1
        )
        
        betting_accuracy = correct_bet_increases / max(profitable_counts, 1)
        
        return {
            'total_hands': total_hands,
            'profitable_count_pct': (profitable_counts / total_hands) * 100,
            'avg_true_count': avg_true_count,
            'betting_accuracy': betting_accuracy,
            'recommended_sessions': self._get_session_recommendations(avg_true_count)
        }
    
    def _get_session_recommendations(self, avg_true_count: float) -> List[str]:
        """Get recommendations based on session analysis"""
        recommendations = []
        
        if avg_true_count > 1:
            recommendations.append("Good counting conditions - continue playing")
        elif avg_true_count > 0:
            recommendations.append("Neutral conditions - monitor closely")
        else:
            recommendations.append("Poor conditions - consider taking breaks")
        
        if avg_true_count < -1:
            recommendations.append("Highly negative counts - reduce exposure")
        
        return recommendations
    
    def simulate_counting_advantage(
        self, 
        true_count: float, 
        num_simulations: int = 10000
    ) -> Dict[str, float]:
        """Simulate expected advantage at given true count"""
        
        # Simplified advantage calculation for Hi-Lo
        # Each point of true count ≈ 0.5% advantage
        player_advantage = (true_count * 0.005) - 0.005  # House edge offset
        
        # Calculate expected return
        expected_return = player_advantage
        win_probability = 0.5 + (player_advantage / 2)  # Simplified
        
        return {
            'player_advantage_pct': player_advantage * 100,
            'expected_return_pct': expected_return * 100,
            'win_probability': win_probability,
            'recommended_action': 'increase_bets' if player_advantage > 0 else 'minimum_bet'
        }


class AdvancedCounting:
    """Advanced counting techniques and systems"""
    
    @staticmethod
    def omega_ii_count(card: Card) -> int:
        """Omega II counting system (more accurate but complex)"""
        omega_values = {
            Rank.TWO: 1, Rank.THREE: 1, Rank.FOUR: 2, Rank.FIVE: 2, Rank.SIX: 2,
            Rank.SEVEN: 1, Rank.EIGHT: 0, Rank.NINE: -1,
            Rank.TEN: -2, Rank.JACK: -2, Rank.QUEEN: -2, Rank.KING: -2, Rank.ACE: 0
        }
        return omega_values[card.rank]
    
    @staticmethod
    def zen_count(card: Card) -> int:
        """Zen counting system"""
        zen_values = {
            Rank.TWO: 1, Rank.THREE: 1, Rank.FOUR: 2, Rank.FIVE: 2, Rank.SIX: 2,
            Rank.SEVEN: 1, Rank.EIGHT: 0, Rank.NINE: 0,
            Rank.TEN: -2, Rank.JACK: -2, Rank.QUEEN: -2, Rank.KING: -2, Rank.ACE: -1
        }
        return zen_values[card.rank]
    
    @staticmethod
    def red_seven_count(card: Card) -> int:
        """Red Seven counting system (easier to learn)"""
        if card.rank == Rank.SEVEN:
            # Only red sevens count as +1
            if card.suit.value in ['♥', '♦']:  # Hearts or Diamonds
                return 1
            else:
                return 0
        
        # Standard Hi-Lo for other cards
        hi_lo_values = {
            Rank.TWO: 1, Rank.THREE: 1, Rank.FOUR: 1, Rank.FIVE: 1, Rank.SIX: 1,
            Rank.EIGHT: 0, Rank.NINE: 0,
            Rank.TEN: -1, Rank.JACK: -1, Rank.QUEEN: -1, Rank.KING: -1, Rank.ACE: -1
        }
        return hi_lo_values.get(card.rank, 0)
    
    def get_system_comparison(self) -> Dict[str, Dict[str, float]]:
        """Compare different counting systems"""
        return {
            'hi_lo': {
                'betting_correlation': 0.97,
                'playing_efficiency': 0.51,
                'insurance_correlation': 0.76,
                'difficulty': 2  # 1-5 scale
            },
            'omega_ii': {
                'betting_correlation': 0.92,
                'playing_efficiency': 0.67,
                'insurance_correlation': 0.85,
                'difficulty': 4
            },
            'zen': {
                'betting_correlation': 0.96,
                'playing_efficiency': 0.54,
                'insurance_correlation': 0.85,
                'difficulty': 4
            },
            'red_seven': {
                'betting_correlation': 0.98,
                'playing_efficiency': 0.54,
                'insurance_correlation': 0.78,
                'difficulty': 1
            }
        }
