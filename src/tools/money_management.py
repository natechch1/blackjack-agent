"""
Bankroll and money management tools for Blackjack AI Agent.
Implements Kelly Criterion, risk assessment, and betting strategies.
"""
import math
from typing import Dict, Any, Tuple, List, Optional
from dataclasses import dataclass
from enum import Enum


class RiskLevel(Enum):
    """Risk tolerance levels"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"  
    AGGRESSIVE = "aggressive"
    PROFESSIONAL = "professional"


@dataclass
class BankrollState:
    """Current bankroll state and metrics"""
    current_bankroll: float
    initial_bankroll: float
    peak_bankroll: float
    current_drawdown: float
    max_drawdown: float
    sessions_played: int
    total_hands: int
    net_profit: float
    win_rate: float
    roi: float


@dataclass
class BetRecommendation:
    """Betting recommendation with explanation"""
    bet_amount: float
    bet_multiplier: float
    reasoning: str
    risk_level: str
    kelly_fraction: float
    max_loss_potential: float


class BankrollManager:
    """Advanced bankroll management system"""
    
    def __init__(
        self,
        initial_bankroll: float,
        base_bet: float,
        risk_level: RiskLevel = RiskLevel.MODERATE
    ):
        self.initial_bankroll = initial_bankroll
        self.current_bankroll = initial_bankroll
        self.base_bet = base_bet
        self.risk_level = risk_level
        
        # Tracking variables
        self.peak_bankroll = initial_bankroll
        self.max_drawdown = 0.0
        self.session_history = []
        self.bet_history = []
        
        # Risk parameters based on risk level
        self.risk_params = self._get_risk_parameters()
    
    def _get_risk_parameters(self) -> Dict[str, float]:
        """Get risk parameters based on risk level"""
        params = {
            RiskLevel.CONSERVATIVE: {
                'kelly_fraction': 0.125,  # 1/8 Kelly
                'max_bet_pct': 0.025,     # 2.5% of bankroll max
                'stop_loss_pct': 0.30,    # 30% loss stop
                'max_bet_multiplier': 4
            },
            RiskLevel.MODERATE: {
                'kelly_fraction': 0.25,   # 1/4 Kelly
                'max_bet_pct': 0.05,      # 5% of bankroll max
                'stop_loss_pct': 0.50,    # 50% loss stop
                'max_bet_multiplier': 8
            },
            RiskLevel.AGGRESSIVE: {
                'kelly_fraction': 0.5,    # 1/2 Kelly
                'max_bet_pct': 0.10,      # 10% of bankroll max
                'stop_loss_pct': 0.70,    # 70% loss stop
                'max_bet_multiplier': 16
            },
            RiskLevel.PROFESSIONAL: {
                'kelly_fraction': 0.75,   # 3/4 Kelly
                'max_bet_pct': 0.15,      # 15% of bankroll max
                'stop_loss_pct': 0.80,    # 80% loss stop
                'max_bet_multiplier': 20
            }
        }
        return params[self.risk_level]
    
    def calculate_kelly_bet(
        self,
        win_probability: float,
        win_amount: float,
        loss_amount: float
    ) -> float:
        """Calculate optimal Kelly bet size"""
        if win_probability <= 0 or win_probability >= 1:
            return 0.0
        
        # Kelly formula: f = (bp - q) / b
        # where: b = odds received, p = win probability, q = loss probability
        b = win_amount / loss_amount  # odds
        p = win_probability
        q = 1 - p
        
        kelly_fraction = (b * p - q) / b
        
        # Apply safety factor
        kelly_fraction *= self.risk_params['kelly_fraction']
        
        # Convert to bet amount
        kelly_bet = self.current_bankroll * kelly_fraction
        
        return max(0, kelly_bet)
    
    def get_count_based_bet(
        self,
        true_count: float,
        player_advantage: Optional[float] = None
    ) -> BetRecommendation:
        """Calculate bet size based on true count"""
        
        # Estimate player advantage if not provided
        if player_advantage is None:
            # Hi-Lo approximation: ~0.5% advantage per true count point
            house_edge = 0.005  # ~0.5% base house edge
            player_advantage = (true_count * 0.005) - house_edge
        
        # No advantage = minimum bet
        if player_advantage <= 0:
            bet_amount = self.base_bet
            return BetRecommendation(
                bet_amount=bet_amount,
                bet_multiplier=1.0,
                reasoning=f"TC {true_count:.1f}: No advantage, minimum bet",
                risk_level=self.risk_level.value,
                kelly_fraction=0,
                max_loss_potential=bet_amount
            )
        
        # Calculate Kelly bet
        win_prob = 0.5 + (player_advantage / 2)  # Simplified conversion
        kelly_bet = self.calculate_kelly_bet(win_prob, 1.0, 1.0)
        
        # Apply count-based multiplier
        count_multiplier = self._get_count_multiplier(true_count)
        suggested_bet = self.base_bet * count_multiplier
        
        # Take minimum of Kelly and count-based methods
        bet_amount = min(kelly_bet, suggested_bet)
        
        # Apply limits
        max_bet = self.current_bankroll * self.risk_params['max_bet_pct']
        max_multiplier_bet = self.base_bet * self.risk_params['max_bet_multiplier']
        
        bet_amount = min(bet_amount, max_bet, max_multiplier_bet)
        bet_amount = max(bet_amount, self.base_bet)  # Never bet less than base
        
        # Round to nearest $5
        bet_amount = round(bet_amount / 5) * 5
        
        return BetRecommendation(
            bet_amount=bet_amount,
            bet_multiplier=bet_amount / self.base_bet,
            reasoning=self._get_betting_reasoning(true_count, player_advantage, bet_amount),
            risk_level=self.risk_level.value,
            kelly_fraction=kelly_bet / self.current_bankroll if self.current_bankroll > 0 else 0,
            max_loss_potential=bet_amount
        )
    
    def _get_count_multiplier(self, true_count: float) -> float:
        """Get betting multiplier based on true count"""
        if true_count <= 1:
            return 1.0
        elif true_count <= 2:
            return 2.0
        elif true_count <= 3:
            return 4.0
        elif true_count <= 4:
            return 6.0
        else:
            return min(self.risk_params['max_bet_multiplier'], true_count * 2)
    
    def _get_betting_reasoning(
        self,
        true_count: float,
        player_advantage: float,
        bet_amount: float
    ) -> str:
        """Generate explanation for betting recommendation"""
        advantage_pct = player_advantage * 100
        multiplier = bet_amount / self.base_bet
        
        reasoning = f"TC {true_count:.1f} (+{advantage_pct:.1f}% advantage): "
        
        if multiplier == 1:
            reasoning += "Minimum bet (no/low advantage)"
        elif multiplier <= 2:
            reasoning += f"{multiplier:.1f}x bet (small advantage)"
        elif multiplier <= 4:
            reasoning += f"{multiplier:.1f}x bet (moderate advantage)"  
        elif multiplier <= 8:
            reasoning += f"{multiplier:.1f}x bet (good advantage)"
        else:
            reasoning += f"{multiplier:.1f}x bet (strong advantage)"
        
        # Add risk level context
        reasoning += f" [{self.risk_level.value} risk profile]"
        
        return reasoning
    
    def update_bankroll(self, result: float, bet_amount: float):
        """Update bankroll after a hand"""
        self.current_bankroll += result
        
        # Update peak and drawdown tracking
        if self.current_bankroll > self.peak_bankroll:
            self.peak_bankroll = self.current_bankroll
        
        current_drawdown = (self.peak_bankroll - self.current_bankroll) / self.peak_bankroll
        self.max_drawdown = max(self.max_drawdown, current_drawdown)
        
        # Record bet history
        self.bet_history.append({
            'bet_amount': bet_amount,
            'result': result,
            'bankroll_after': self.current_bankroll,
            'drawdown': current_drawdown
        })
    
    def get_bankroll_state(self) -> BankrollState:
        """Get current bankroll state and metrics"""
        total_hands = len(self.bet_history)
        
        if total_hands > 0:
            net_profit = self.current_bankroll - self.initial_bankroll
            wins = sum(1 for bet in self.bet_history if bet['result'] > 0)
            win_rate = wins / total_hands
            roi = net_profit / self.initial_bankroll
        else:
            net_profit = 0
            win_rate = 0
            roi = 0
        
        current_drawdown = (self.peak_bankroll - self.current_bankroll) / self.peak_bankroll
        
        return BankrollState(
            current_bankroll=self.current_bankroll,
            initial_bankroll=self.initial_bankroll,
            peak_bankroll=self.peak_bankroll,
            current_drawdown=current_drawdown,
            max_drawdown=self.max_drawdown,
            sessions_played=len(self.session_history),
            total_hands=total_hands,
            net_profit=net_profit,
            win_rate=win_rate,
            roi=roi
        )
    
    def should_stop_session(self) -> Tuple[bool, str]:
        """Determine if session should be stopped due to losses"""
        current_loss_pct = (self.initial_bankroll - self.current_bankroll) / self.initial_bankroll
        
        if current_loss_pct >= self.risk_params['stop_loss_pct']:
            return True, f"Stop-loss triggered: {current_loss_pct:.1%} loss exceeds {self.risk_params['stop_loss_pct']:.1%} limit"
        
        # Check if bankroll is too low for meaningful betting
        if self.current_bankroll < self.base_bet * 20:
            return True, f"Bankroll too low: ${self.current_bankroll:.0f} < 20x base bet"
        
        return False, "Continue playing"
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session"""
        if not self.bet_history:
            return {"message": "No hands played yet"}
        
        session_start_bankroll = self.bet_history[0]['bankroll_after'] - self.bet_history[0]['result']
        session_profit = self.current_bankroll - session_start_bankroll
        
        total_wagered = sum(abs(bet['bet_amount']) for bet in self.bet_history)
        wins = sum(1 for bet in self.bet_history if bet['result'] > 0)
        losses = sum(1 for bet in self.bet_history if bet['result'] < 0)
        pushes = len(self.bet_history) - wins - losses
        
        return {
            'hands_played': len(self.bet_history),
            'session_profit': session_profit,
            'total_wagered': total_wagered,
            'win_rate': wins / len(self.bet_history) if self.bet_history else 0,
            'wins': wins,
            'losses': losses,
            'pushes': pushes,
            'average_bet': total_wagered / len(self.bet_history) if self.bet_history else 0,
            'roi_session': session_profit / total_wagered if total_wagered > 0 else 0
        }
    
    def optimize_base_bet(self, target_ruin_probability: float = 0.01) -> float:
        """Optimize base bet size to achieve target ruin probability"""
        # Simplified risk of ruin calculation
        # Assumes known win rate and average advantage
        
        state = self.get_bankroll_state()
        
        if state.total_hands < 100:
            return self.base_bet  # Not enough data
        
        # Estimate sustainable bet size
        win_rate = state.win_rate
        avg_advantage = (state.roi * self.initial_bankroll) / (state.total_hands * self.base_bet)
        
        if avg_advantage <= 0:
            return self.base_bet * 0.5  # Reduce bet if losing
        
        # Simplified Kelly criterion for sustainable betting
        optimal_fraction = avg_advantage / (1 + avg_advantage)
        optimal_fraction *= self.risk_params['kelly_fraction']  # Apply safety factor
        
        optimal_base_bet = self.current_bankroll * optimal_fraction / 4  # Conservative divisor
        
        return max(self.base_bet * 0.5, min(optimal_base_bet, self.base_bet * 2))
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive risk metrics"""
        if not self.bet_history:
            return {"message": "No data available"}
        
        returns = [bet['result'] / bet['bet_amount'] for bet in self.bet_history]
        
        # Calculate volatility
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        volatility = math.sqrt(variance)
        
        # Sharpe ratio (simplified)
        if volatility > 0:
            sharpe_ratio = avg_return / volatility
        else:
            sharpe_ratio = 0
        
        # Value at Risk (5%)
        sorted_returns = sorted(returns)
        var_5_pct = sorted_returns[max(0, int(len(sorted_returns) * 0.05) - 1)]
        
        return {
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'value_at_risk_5pct': var_5_pct,
            'max_single_loss': min(returns),
            'max_single_win': max(returns),
            'current_drawdown_pct': self.get_bankroll_state().current_drawdown * 100,
            'max_drawdown_pct': self.max_drawdown * 100,
            'bankroll_at_risk': self.current_bankroll * var_5_pct if var_5_pct < 0 else 0
        }


class AdvancedBankrollStrategies:
    """Advanced bankroll management strategies"""
    
    @staticmethod
    def calculate_required_bankroll(
        base_bet: float,
        win_rate: float,
        average_win: float,
        ruin_probability: float = 0.01,
        confidence_level: float = 0.95
    ) -> Dict[str, float]:
        """Calculate required bankroll for given ruin probability"""
        
        # Simplified bankroll calculation
        # In practice, this would use more sophisticated models
        
        if win_rate <= 0.5:
            # Negative expectation game
            return {
                'required_bankroll': float('inf'),
                'recommendation': 'Do not play - negative expectation'
            }
        
        # Estimate required bankroll as multiple of base bet
        edge = (win_rate * average_win) - ((1 - win_rate) * 1)
        
        if edge <= 0:
            multiplier = float('inf')
        else:
            # Simplified calculation based on Kelly and ruin probability
            kelly_fraction = edge
            multiplier = int(-math.log(ruin_probability) / kelly_fraction)
        
        required_bankroll = base_bet * multiplier
        
        return {
            'required_bankroll': required_bankroll,
            'bankroll_multiplier': multiplier,
            'player_edge': edge,
            'kelly_fraction': kelly_fraction,
            'confidence_level': confidence_level
        }
    
    @staticmethod
    def simulate_drawdown_distribution(
        initial_bankroll: float,
        base_bet: float,
        win_rate: float,
        num_simulations: int = 1000,
        max_hands: int = 10000
    ) -> Dict[str, Any]:
        """Simulate distribution of maximum drawdowns"""
        
        import random
        
        max_drawdowns = []
        
        for _ in range(num_simulations):
            bankroll = initial_bankroll
            peak = initial_bankroll
            max_dd = 0
            
            for _ in range(max_hands):
                # Simulate hand outcome
                if random.random() < win_rate:
                    bankroll += base_bet
                else:
                    bankroll -= base_bet
                
                # Update peak and drawdown
                if bankroll > peak:
                    peak = bankroll
                
                drawdown = (peak - bankroll) / peak
                max_dd = max(max_dd, drawdown)
                
                # Stop if bankroll exhausted
                if bankroll <= 0:
                    max_dd = 1.0
                    break
            
            max_drawdowns.append(max_dd)
        
        # Calculate statistics
        max_drawdowns.sort()
        
        return {
            'mean_max_drawdown': sum(max_drawdowns) / len(max_drawdowns),
            'median_max_drawdown': max_drawdowns[len(max_drawdowns) // 2],
            'worst_case_drawdown': max(max_drawdowns),
            'percentile_95': max_drawdowns[int(len(max_drawdowns) * 0.95)],
            'percentile_99': max_drawdowns[int(len(max_drawdowns) * 0.99)],
            'ruin_probability': sum(1 for dd in max_drawdowns if dd >= 1.0) / len(max_drawdowns)
        }
