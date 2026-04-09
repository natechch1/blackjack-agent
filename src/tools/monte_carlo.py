"""
Monte Carlo simulation tools for Blackjack probability analysis.
"""
import random
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp

from ..game.cards import Card, Rank, Suit, Hand
from ..game.blackjack_env import BlackjackEnvironment, Action, GameResult


@dataclass
class SimulationResult:
    """Result of Monte Carlo simulation"""
    win_probability: float
    lose_probability: float
    push_probability: float
    blackjack_probability: float
    expected_value: float
    confidence_interval: Tuple[float, float]
    num_simulations: int
    scenario: str


class MonteCarloSimulator:
    """Monte Carlo simulation engine for Blackjack scenarios"""
    
    def __init__(self, num_processes: Optional[int] = None):
        self.num_processes = num_processes or max(1, mp.cpu_count() - 1)
    
    def simulate_hand_outcome(
        self, 
        player_cards: List[Card], 
        dealer_upcard: Card,
        num_simulations: int = 10000,
        action: Action = Action.STAND,
        game_config: Optional[Dict] = None
    ) -> SimulationResult:
        """
        Simulate outcomes for a specific hand scenario
        """
        scenario_desc = f"Player {self._cards_to_string(player_cards)} vs Dealer {dealer_upcard}"
        
        # Split simulations across processes
        sims_per_process = num_simulations // self.num_processes
        remaining_sims = num_simulations % self.num_processes
        
        simulation_batches = [sims_per_process] * self.num_processes
        if remaining_sims:
            simulation_batches[0] += remaining_sims
        
        # Run parallel simulations
        with ProcessPoolExecutor(max_workers=self.num_processes) as executor:
            futures = [
                executor.submit(
                    self._simulate_batch,
                    player_cards,
                    dealer_upcard,
                    batch_size,
                    action,
                    game_config
                )
                for batch_size in simulation_batches
            ]
            
            # Combine results
            all_outcomes = []
            for future in futures:
                batch_outcomes = future.result()
                all_outcomes.extend(batch_outcomes)
        
        # Analyze results
        return self._analyze_simulation_results(all_outcomes, scenario_desc, num_simulations)
    
    def _simulate_batch(
        self,
        player_cards: List[Card],
        dealer_upcard: Card,
        batch_size: int,
        action: Action,
        game_config: Optional[Dict]
    ) -> List[GameResult]:
        """Run a batch of simulations in a single process"""
        outcomes = []
        
        for _ in range(batch_size):
            # Create fresh environment for each simulation
            env = BlackjackEnvironment()
            if game_config:
                env.config.update(game_config)
            
            # Setup scenario
            outcome = self._simulate_single_hand(
                env, player_cards, dealer_upcard, action
            )
            outcomes.append(outcome)
        
        return outcomes
    
    def _simulate_single_hand(
        self,
        env: BlackjackEnvironment,
        player_cards: List[Card],
        dealer_upcard: Card,
        action: Action
    ) -> GameResult:
        """Simulate a single hand to completion"""
        
        # Create a new shoe and set it up
        env.shoe.reset()
        
        # Remove known cards from shoe
        known_cards = player_cards + [dealer_upcard]
        for card in known_cards:
            # Find and remove the card from shoe
            for i, shoe_card in enumerate(env.shoe.cards):
                if (shoe_card.rank == card.rank and 
                    shoe_card.suit == card.suit):
                    env.shoe.cards.pop(i)
                    break
        
        # Set up game state
        game_state = env.game_state
        game_state.player_hands = [Hand()]
        game_state.dealer_hand = Hand()
        
        # Add known player cards
        for card in player_cards:
            game_state.player_hands[0].add_card(card)
        
        # Add dealer upcard
        game_state.dealer_hand.add_card(dealer_upcard)
        
        # Deal dealer hole card
        hole_card = env.shoe.deal_card()
        if hole_card:
            game_state.dealer_hand.add_card(hole_card)
        
        # Execute player action
        player_hand = game_state.player_hands[0]
        
        if action == Action.HIT:
            # Keep hitting until stand or bust
            while player_hand.value < 21:
                card = env.shoe.deal_card()
                if card:
                    player_hand.add_card(card)
                else:
                    break
                # Simple strategy: hit until 17
                if player_hand.value >= 17:
                    break
        elif action == Action.DOUBLE:
            # Hit exactly once
            card = env.shoe.deal_card()
            if card:
                player_hand.add_card(card)
        # STAND does nothing
        
        # Play dealer
        game_state.current_hand_index = 1  # Mark player done
        env.play_dealer()
        
        # Calculate result
        results = env.calculate_results()
        if results:
            return results[0][0]  # First hand result
        
        return GameResult.LOSE  # Fallback
    
    def _analyze_simulation_results(
        self,
        outcomes: List[GameResult],
        scenario: str,
        num_simulations: int
    ) -> SimulationResult:
        """Analyze simulation outcomes and calculate statistics"""
        
        # Count outcomes
        outcome_counts = {
            GameResult.WIN: outcomes.count(GameResult.WIN),
            GameResult.LOSE: outcomes.count(GameResult.LOSE),
            GameResult.PUSH: outcomes.count(GameResult.PUSH),
            GameResult.BLACKJACK: outcomes.count(GameResult.BLACKJACK),
        }
        
        # Calculate probabilities
        total = len(outcomes)
        win_prob = outcome_counts[GameResult.WIN] / total
        lose_prob = outcome_counts[GameResult.LOSE] / total
        push_prob = outcome_counts[GameResult.PUSH] / total
        bj_prob = outcome_counts[GameResult.BLACKJACK] / total
        
        # Calculate expected value (simplified)
        expected_value = (
            win_prob * 1.0 +           # Win: +1 unit
            bj_prob * 1.5 +            # Blackjack: +1.5 units
            push_prob * 0.0 +          # Push: 0 units
            lose_prob * (-1.0)         # Lose: -1 unit
        )
        
        # Calculate confidence interval for win probability (95%)
        std_error = np.sqrt(win_prob * (1 - win_prob) / total)
        margin_error = 1.96 * std_error
        confidence_interval = (
            max(0, win_prob - margin_error),
            min(1, win_prob + margin_error)
        )
        
        return SimulationResult(
            win_probability=win_prob,
            lose_probability=lose_prob,
            push_probability=push_prob,
            blackjack_probability=bj_prob,
            expected_value=expected_value,
            confidence_interval=confidence_interval,
            num_simulations=num_simulations,
            scenario=scenario
        )
    
    def compare_actions(
        self,
        player_cards: List[Card],
        dealer_upcard: Card,
        actions: List[Action],
        num_simulations: int = 5000
    ) -> Dict[Action, SimulationResult]:
        """Compare expected outcomes for different actions"""
        
        results = {}
        
        for action in actions:
            result = self.simulate_hand_outcome(
                player_cards, dealer_upcard, num_simulations, action
            )
            results[action] = result
        
        return results
    
    def analyze_basic_strategy_accuracy(
        self,
        test_scenarios: List[Dict[str, Any]],
        num_simulations: int = 1000
    ) -> Dict[str, Any]:
        """Test basic strategy recommendations against simulation"""
        
        accurate_recommendations = 0
        total_scenarios = len(test_scenarios)
        
        detailed_results = []
        
        for scenario in test_scenarios:
            player_cards = scenario['player_cards']
            dealer_upcard = scenario['dealer_upcard']
            recommended_action = scenario['recommended_action']
            
            # Simulate all possible actions
            possible_actions = [Action.HIT, Action.STAND]
            if scenario.get('can_double', False):
                possible_actions.append(Action.DOUBLE)
            
            action_results = self.compare_actions(
                player_cards, dealer_upcard, possible_actions, num_simulations
            )
            
            # Find best action by expected value
            best_action = max(
                action_results.keys(),
                key=lambda a: action_results[a].expected_value
            )
            
            # Check if recommendation matches simulation
            is_accurate = (recommended_action == best_action)
            accurate_recommendations += is_accurate
            
            detailed_results.append({
                'scenario': self._cards_to_string(player_cards) + f" vs {dealer_upcard}",
                'recommended': recommended_action.value,
                'simulated_best': best_action.value,
                'accurate': is_accurate,
                'ev_difference': (
                    action_results[recommended_action].expected_value - 
                    action_results[best_action].expected_value
                )
            })
        
        accuracy = accurate_recommendations / total_scenarios
        
        return {
            'accuracy_percentage': accuracy * 100,
            'accurate_count': accurate_recommendations,
            'total_scenarios': total_scenarios,
            'detailed_results': detailed_results
        }
    
    def simulate_counting_advantage(
        self,
        true_count: float,
        num_hands: int = 1000
    ) -> Dict[str, float]:
        """Simulate the advantage gained from card counting"""
        
        # This is a simplified simulation
        # In reality, you'd need to simulate with actual remaining cards
        
        # Approximate advantage per true count point (Hi-Lo system)
        base_house_edge = 0.005  # ~0.5% house edge
        counting_advantage = true_count * 0.005  # ~0.5% per TC point
        
        player_advantage = counting_advantage - base_house_edge
        
        # Simulate hands with this advantage
        wins = 0
        total_bet_value = 0
        
        for _ in range(num_hands):
            # Random outcome based on advantage
            if random.random() < (0.5 + player_advantage / 2):
                wins += 1
            total_bet_value += 1
        
        actual_advantage = (wins / num_hands - 0.5) * 2
        
        return {
            'theoretical_advantage': player_advantage,
            'simulated_advantage': actual_advantage,
            'win_rate': wins / num_hands,
            'expected_hourly_profit': player_advantage * 100,  # Per 100 hands
            'recommendation': 'increase_bets' if player_advantage > 0.01 else 'minimum_bet'
        }
    
    def _cards_to_string(self, cards: List[Card]) -> str:
        """Convert list of cards to readable string"""
        return ", ".join(str(card) for card in cards)


class AdvancedSimulation:
    """Advanced simulation scenarios"""
    
    @staticmethod
    def simulate_session_variance(
        base_bet: float,
        num_sessions: int = 1000,
        hands_per_session: int = 100,
        player_advantage: float = 0.01
    ) -> Dict[str, Any]:
        """Simulate bankroll variance over multiple sessions"""
        
        session_results = []
        
        for _ in range(num_sessions):
            session_profit = 0
            
            for _ in range(hands_per_session):
                # Simulate single hand
                if random.random() < (0.5 + player_advantage):
                    session_profit += base_bet
                else:
                    session_profit -= base_bet
            
            session_results.append(session_profit)
        
        # Calculate statistics
        avg_profit = np.mean(session_results)
        std_dev = np.std(session_results)
        
        # Risk metrics
        var_95 = np.percentile(session_results, 5)  # 95% VaR
        max_drawdown = min(session_results)
        
        return {
            'average_session_profit': avg_profit,
            'standard_deviation': std_dev,
            'worst_session': max_drawdown,
            'best_session': max(session_results),
            'value_at_risk_95': var_95,
            'probability_of_loss': sum(1 for x in session_results if x < 0) / num_sessions,
            'recommended_bankroll': abs(var_95) * 20  # 20x worst 5% outcome
        }
    
    @staticmethod
    def analyze_penetration_impact(
        penetrations: List[float] = [0.5, 0.65, 0.75, 0.85],
        true_count: float = 2.0
    ) -> Dict[float, Dict[str, float]]:
        """Analyze how shoe penetration affects counting advantage"""
        
        results = {}
        
        for penetration in penetrations:
            # Simplified model: deeper penetration = more reliable count
            count_reliability = penetration ** 2  # Exponential improvement
            
            effective_advantage = true_count * 0.005 * count_reliability
            
            results[penetration] = {
                'count_reliability': count_reliability,
                'effective_advantage': effective_advantage,
                'hourly_ev': effective_advantage * 100,  # Per 100 hands
                'recommended_bet_multiplier': max(1, int(effective_advantage * 200))
            }
        
        return results
