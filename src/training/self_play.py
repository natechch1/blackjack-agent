"""
Self-play training system for Blackjack AI Agent.
Optimizes decision thresholds without retraining the LLM.
"""
import json
import os
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import itertools
from concurrent.futures import ProcessPoolExecutor
import random

from ..agent.blackjack_agent import BlackjackAgent
from ..game.blackjack_env import BlackjackEnvironment, Action
from ..game.cards import Hand, Card, Rank
from ..tools.basic_strategy import BasicStrategy


@dataclass
class TrainingScenario:
    """Training scenario definition"""
    player_total: int
    is_soft: bool
    is_pair: bool
    dealer_upcard_value: int
    true_count_range: Tuple[float, float]
    decision_threshold: str
    current_value: float
    test_values: List[float]


@dataclass
class TrainingResult:
    """Result of a training scenario"""
    scenario: TrainingScenario
    optimal_threshold: float
    expected_value_improvement: float
    confidence_interval: Tuple[float, float]
    hands_simulated: int
    win_rate_improvement: float


class SelfPlayTrainer:
    """Self-play training system"""
    
    def __init__(
        self, 
        config_path: Optional[str] = None,
        parallel_processes: int = 4
    ):
        self.config_path = config_path
        self.parallel_processes = parallel_processes
        self.training_scenarios = self._define_training_scenarios()
        self.results_history = []
        self.current_overrides = {}
        
    def _define_training_scenarios(self) -> List[TrainingScenario]:
        """Define key decision scenarios for optimization"""
        scenarios = []
        
        # Critical marginal decisions from basic strategy
        critical_decisions = [
            # Hard hands vs borderline dealer cards
            {"player": 12, "dealer": 2, "soft": False, "pair": False, "threshold": "stand_threshold"},
            {"player": 12, "dealer": 3, "soft": False, "pair": False, "threshold": "stand_threshold"},
            {"player": 13, "dealer": 2, "soft": False, "pair": False, "threshold": "stand_threshold"},
            {"player": 16, "dealer": 10, "soft": False, "pair": False, "threshold": "surrender_threshold"},
            {"player": 15, "dealer": 10, "soft": False, "pair": False, "threshold": "surrender_threshold"},
            
            # Soft hands - most variable decisions
            {"player": 18, "dealer": 6, "soft": True, "pair": False, "threshold": "double_threshold"},
            {"player": 18, "dealer": 9, "soft": True, "pair": False, "threshold": "hit_threshold"},
            {"player": 18, "dealer": 10, "soft": True, "pair": False, "threshold": "hit_threshold"},
            {"player": 17, "dealer": 6, "soft": True, "pair": False, "threshold": "double_threshold"},
            {"player": 16, "dealer": 5, "soft": True, "pair": False, "threshold": "double_threshold"},
            
            # Doubling decisions
            {"player": 9, "dealer": 2, "soft": False, "pair": False, "threshold": "double_threshold"},
            {"player": 10, "dealer": 10, "soft": False, "pair": False, "threshold": "double_threshold"},
            {"player": 11, "dealer": 11, "soft": False, "pair": False, "threshold": "double_threshold"},
            
            # Pair splitting
            {"player": 20, "dealer": 5, "soft": False, "pair": True, "threshold": "split_threshold"},  # 10s vs 5
            {"player": 12, "dealer": 7, "soft": False, "pair": True, "threshold": "split_threshold"},  # 6s vs 7
            {"player": 14, "dealer": 8, "soft": False, "pair": True, "threshold": "split_threshold"},  # 7s vs 8
        ]
        
        for decision in critical_decisions:
            # Test different true count ranges
            count_ranges = [(-2, 0), (0, 2), (2, 4), (4, 6)]
            
            for count_range in count_ranges:
                scenario = TrainingScenario(
                    player_total=decision["player"],
                    is_soft=decision["soft"],
                    is_pair=decision["pair"],
                    dealer_upcard_value=decision["dealer"],
                    true_count_range=count_range,
                    decision_threshold=decision["threshold"],
                    current_value=0.0,  # Will be set during training
                    test_values=list(np.arange(-3, 6, 0.5))  # Test thresholds
                )
                scenarios.append(scenario)
        
        return scenarios
    
    def train(
        self,
        episodes: int = 50000,
        optimization_rounds: int = 10,
        save_results: bool = True
    ) -> Dict[str, Any]:
        """Run self-play training to optimize decision thresholds"""
        
        training_start = datetime.now()
        
        print(f"Starting self-play training with {episodes} episodes over {optimization_rounds} rounds")
        print(f"Training {len(self.training_scenarios)} scenarios")
        
        # Initialize baseline performance
        baseline_performance = self._evaluate_current_strategy(episodes // 10)
        
        optimization_results = []
        
        for round_num in range(optimization_rounds):
            print(f"\n--- Optimization Round {round_num + 1}/{optimization_rounds} ---")
            
            round_results = []
            
            # Optimize each scenario
            for i, scenario in enumerate(self.training_scenarios):
                print(f"Optimizing scenario {i + 1}/{len(self.training_scenarios)}: "
                      f"{scenario.player_total}{'(soft)' if scenario.is_soft else ''}{'(pair)' if scenario.is_pair else ''} "
                      f"vs {scenario.dealer_upcard_value} TC:{scenario.true_count_range}")
                
                # Optimize this scenario
                result = self._optimize_scenario(scenario, episodes // len(self.training_scenarios))
                round_results.append(result)
                
                # Update overrides if improvement found
                if result.expected_value_improvement > 0.001:  # Minimum improvement threshold
                    self._update_overrides(result)
            
            optimization_results.append(round_results)
            
            # Evaluate overall improvement
            current_performance = self._evaluate_current_strategy(episodes // 10)
            improvement = current_performance['expected_value'] - baseline_performance['expected_value']
            
            print(f"Round {round_num + 1} improvement: {improvement:.4f} EV units")
        
        # Final evaluation
        final_performance = self._evaluate_current_strategy(episodes // 5)
        total_improvement = final_performance['expected_value'] - baseline_performance['expected_value']
        
        training_summary = {
            'training_start': training_start.isoformat(),
            'training_end': datetime.now().isoformat(),
            'episodes_total': episodes,
            'optimization_rounds': optimization_rounds,
            'scenarios_tested': len(self.training_scenarios),
            'baseline_performance': baseline_performance,
            'final_performance': final_performance,
            'total_improvement': total_improvement,
            'optimization_results': optimization_results,
            'final_overrides': self.current_overrides
        }
        
        if save_results:
            self._save_training_results(training_summary)
        
        print(f"\nTraining complete! Total EV improvement: {total_improvement:.4f}")
        
        return training_summary
    
    def _optimize_scenario(self, scenario: TrainingScenario, episodes: int) -> TrainingResult:
        """Optimize a specific decision scenario"""
        
        threshold_results = []
        
        # Test different threshold values in parallel
        with ProcessPoolExecutor(max_workers=self.parallel_processes) as executor:
            futures = []
            
            for threshold_value in scenario.test_values:
                future = executor.submit(
                    self._test_threshold,
                    scenario,
                    threshold_value,
                    episodes
                )
                futures.append((threshold_value, future))
            
            # Collect results
            for threshold_value, future in futures:
                ev, win_rate, hands = future.result()
                threshold_results.append({
                    'threshold': threshold_value,
                    'expected_value': ev,
                    'win_rate': win_rate,
                    'hands_simulated': hands
                })
        
        # Find optimal threshold
        best_result = max(threshold_results, key=lambda x: x['expected_value'])
        current_result = min(threshold_results, key=lambda x: abs(x['threshold'] - scenario.current_value))
        
        improvement = best_result['expected_value'] - current_result['expected_value']
        win_rate_improvement = best_result['win_rate'] - current_result['win_rate']
        
        return TrainingResult(
            scenario=scenario,
            optimal_threshold=best_result['threshold'],
            expected_value_improvement=improvement,
            confidence_interval=(0, 0),  # Simplified for now
            hands_simulated=sum(r['hands_simulated'] for r in threshold_results),
            win_rate_improvement=win_rate_improvement
        )
    
    def _test_threshold(
        self,
        scenario: TrainingScenario,
        threshold_value: float,
        episodes: int
    ) -> Tuple[float, float, int]:
        """Test a specific threshold value for a scenario"""
        
        # Create temporary agent with modified thresholds
        agent = BlackjackAgent(config_path=self.config_path)
        
        # Apply threshold modification (simplified)
        modified_overrides = self.current_overrides.copy()
        scenario_key = self._get_scenario_key(scenario)
        
        # Determine action based on threshold
        action = self._threshold_to_action(scenario, threshold_value)
        modified_overrides[scenario_key] = {
            "action": action,
            "threshold": threshold_value,
            "reason": f"Optimized threshold: {threshold_value}"
        }
        
        # Update agent's strategy overrides
        agent.basic_strategy.overrides = modified_overrides
        
        # Run simulation
        total_ev = 0
        wins = 0
        hands_played = 0
        
        for _ in range(episodes):
            # Set up specific scenario
            if self._scenario_matches(agent.env.game_state, scenario):
                hand_result = agent.play_hand()
                
                # Extract result
                net_result = hand_result.get('net_result', 0)
                bet_amount = hand_result.get('initial_bet', 25)
                
                if bet_amount > 0:
                    ev_contribution = net_result / bet_amount
                    total_ev += ev_contribution
                    
                    if net_result > 0:
                        wins += 1
                    
                    hands_played += 1
        
        avg_ev = total_ev / max(hands_played, 1)
        win_rate = wins / max(hands_played, 1)
        
        return avg_ev, win_rate, hands_played
    
    def _scenario_matches(self, game_state, scenario: TrainingScenario) -> bool:
        """Check if current game state matches training scenario"""
        # This is simplified - in practice, you'd want more sophisticated matching
        try:
            if not game_state.player_hands:
                return False
            
            hand = game_state.player_hands[0]
            dealer_upcard = game_state.dealer_hand.cards[0] if game_state.dealer_hand.cards else None
            
            if not dealer_upcard:
                return False
            
            # Check hand conditions
            if (hand.value == scenario.player_total and 
                hand.is_soft == scenario.is_soft and
                hand.is_pair == scenario.is_pair):
                
                # Check dealer upcard
                dealer_value = dealer_upcard.value if dealer_upcard.rank != Rank.ACE else 11
                if dealer_value == scenario.dealer_upcard_value:
                    
                    # Check true count range
                    true_count = game_state.shoe.true_count if game_state.shoe else 0
                    if scenario.true_count_range[0] <= true_count <= scenario.true_count_range[1]:
                        return True
            
            return False
            
        except Exception:
            return False
    
    def _get_scenario_key(self, scenario: TrainingScenario) -> str:
        """Generate key for scenario overrides"""
        hand_type = "soft" if scenario.is_soft else ("pair" if scenario.is_pair else "hard")
        return f"{hand_type}_{scenario.player_total}_vs_{scenario.dealer_upcard_value}_tc_{scenario.true_count_range[0]}_{scenario.true_count_range[1]}"
    
    def _threshold_to_action(self, scenario: TrainingScenario, threshold: float) -> str:
        """Convert threshold value to action based on scenario type"""
        
        if scenario.decision_threshold == "stand_threshold":
            return "stand" if threshold > 0 else "hit"
        elif scenario.decision_threshold == "double_threshold":
            return "double" if threshold > 0 else "hit"
        elif scenario.decision_threshold == "split_threshold":
            return "split" if threshold > 0 else "stand"
        elif scenario.decision_threshold == "surrender_threshold":
            return "surrender" if threshold > 0 else "hit"
        elif scenario.decision_threshold == "hit_threshold":
            return "hit" if threshold > 0 else "stand"
        else:
            return "stand"  # Default
    
    def _update_overrides(self, result: TrainingResult):
        """Update strategy overrides based on training result"""
        scenario_key = self._get_scenario_key(result.scenario)
        action = self._threshold_to_action(result.scenario, result.optimal_threshold)
        
        self.current_overrides[scenario_key] = {
            "action": action,
            "threshold": result.optimal_threshold,
            "expected_value_improvement": result.expected_value_improvement,
            "confidence": 0.8,  # Training-based confidence
            "reason": f"Self-play optimized: +{result.expected_value_improvement:.4f} EV"
        }
    
    def _evaluate_current_strategy(self, episodes: int) -> Dict[str, Any]:
        """Evaluate current strategy performance"""
        agent = BlackjackAgent(config_path=self.config_path)
        agent.basic_strategy.overrides = self.current_overrides
        
        session_result = agent.play_session(episodes)
        
        return {
            'expected_value': session_result['bankroll_summary'].get('roi_session', 0),
            'win_rate': session_result['bankroll_summary'].get('win_rate', 0),
            'hands_played': session_result['hands_played'],
            'final_bankroll': session_result['final_state'].current_bankroll
        }
    
    def _save_training_results(self, training_summary: Dict[str, Any]):
        """Save training results to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Ensure directories exist
        os.makedirs("data/training", exist_ok=True)
        os.makedirs("models", exist_ok=True)
        
        # Save full training results
        results_file = f"data/training/training_results_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(training_summary, f, indent=2, default=str)
        
        # Save strategy overrides
        overrides_file = "models/overrides.json"
        with open(overrides_file, 'w') as f:
            json.dump(self.current_overrides, f, indent=2)
        
        # Save human-readable summary
        summary_file = f"data/training/training_summary_{timestamp}.txt"
        with open(summary_file, 'w') as f:
            f.write(f"Blackjack AI Self-Play Training Results\n")
            f.write(f"{'='*50}\n\n")
            f.write(f"Training Date: {training_summary['training_start']}\n")
            f.write(f"Episodes: {training_summary['episodes_total']}\n")
            f.write(f"Scenarios: {training_summary['scenarios_tested']}\n")
            f.write(f"Total EV Improvement: {training_summary['total_improvement']:.4f}\n\n")
            
            f.write("Optimized Overrides:\n")
            f.write("-" * 20 + "\n")
            for key, override in self.current_overrides.items():
                f.write(f"{key}: {override['action']} (+{override['expected_value_improvement']:.4f} EV)\n")
        
        print(f"Training results saved to {results_file}")
        print(f"Strategy overrides saved to {overrides_file}")


class EpsilonGreedyOptimizer:
    """Epsilon-greedy exploration for threshold optimization"""
    
    def __init__(self, epsilon: float = 0.1, decay_rate: float = 0.99):
        self.epsilon = epsilon
        self.decay_rate = decay_rate
        self.action_values = {}
        self.action_counts = {}
    
    def select_threshold(
        self, 
        scenario_key: str, 
        possible_thresholds: List[float]
    ) -> float:
        """Select threshold using epsilon-greedy strategy"""
        
        if scenario_key not in self.action_values:
            self.action_values[scenario_key] = {t: 0.0 for t in possible_thresholds}
            self.action_counts[scenario_key] = {t: 0 for t in possible_thresholds}
        
        # Exploration vs exploitation
        if random.random() < self.epsilon:
            # Explore: random threshold
            return random.choice(possible_thresholds)
        else:
            # Exploit: best known threshold
            best_threshold = max(
                self.action_values[scenario_key].keys(),
                key=lambda t: self.action_values[scenario_key][t]
            )
            return best_threshold
    
    def update_value(
        self, 
        scenario_key: str, 
        threshold: float, 
        reward: float
    ):
        """Update action value using incremental mean"""
        if scenario_key not in self.action_values:
            return
        
        count = self.action_counts[scenario_key][threshold] + 1
        self.action_counts[scenario_key][threshold] = count
        
        # Incremental mean update
        old_value = self.action_values[scenario_key][threshold]
        self.action_values[scenario_key][threshold] = old_value + (reward - old_value) / count
        
        # Decay epsilon
        self.epsilon *= self.decay_rate


class AdvancedTrainingAnalytics:
    """Advanced analytics for training results"""
    
    @staticmethod
    def analyze_convergence(training_history: List[Dict]) -> Dict[str, Any]:
        """Analyze convergence patterns in training"""
        if not training_history:
            return {"message": "No training history available"}
        
        # Extract EV improvements over time
        ev_improvements = []
        for round_results in training_history:
            round_improvement = sum(r.expected_value_improvement for r in round_results)
            ev_improvements.append(round_improvement)
        
        # Calculate convergence metrics
        final_improvements = ev_improvements[-3:] if len(ev_improvements) >= 3 else ev_improvements
        avg_final_improvement = sum(final_improvements) / len(final_improvements)
        
        is_converged = (
            len(ev_improvements) >= 5 and 
            all(abs(imp - avg_final_improvement) < 0.001 for imp in final_improvements)
        )
        
        return {
            'is_converged': is_converged,
            'convergence_round': len(ev_improvements) if is_converged else None,
            'final_improvement_rate': avg_final_improvement,
            'total_rounds': len(ev_improvements),
            'improvement_history': ev_improvements
        }
    
    @staticmethod
    def identify_key_scenarios(
        training_results: List[TrainingResult]
    ) -> List[Dict[str, Any]]:
        """Identify most impactful training scenarios"""
        
        # Sort by improvement
        sorted_results = sorted(
            training_results, 
            key=lambda r: r.expected_value_improvement, 
            reverse=True
        )
        
        key_scenarios = []
        for result in sorted_results[:10]:  # Top 10
            key_scenarios.append({
                'scenario_description': f"{result.scenario.player_total}{'(soft)' if result.scenario.is_soft else ''} vs {result.scenario.dealer_upcard_value}",
                'improvement': result.expected_value_improvement,
                'optimal_threshold': result.optimal_threshold,
                'hands_simulated': result.hands_simulated,
                'decision_type': result.scenario.decision_threshold
            })
        
        return key_scenarios
    
    @staticmethod
    def generate_training_report(training_summary: Dict[str, Any]) -> str:
        """Generate comprehensive training report"""
        
        report = f"""
BLACKJACK AI TRAINING REPORT
{'='*50}

Training Summary:
- Start Time: {training_summary['training_start']}
- Episodes: {training_summary['episodes_total']:,}
- Scenarios: {training_summary['scenarios_tested']}
- Total EV Improvement: {training_summary['total_improvement']:.4f}

Performance Comparison:
- Baseline EV: {training_summary['baseline_performance']['expected_value']:.4f}
- Final EV: {training_summary['final_performance']['expected_value']:.4f}
- Improvement: {training_summary['total_improvement']:.4f} ({training_summary['total_improvement']/abs(training_summary['baseline_performance']['expected_value'])*100:.1f}%)

Key Optimizations:
"""
        
        # Add top improvements
        if training_summary.get('final_overrides'):
            sorted_overrides = sorted(
                training_summary['final_overrides'].items(),
                key=lambda x: x[1].get('expected_value_improvement', 0),
                reverse=True
            )
            
            for i, (scenario, override) in enumerate(sorted_overrides[:5]):
                improvement = override.get('expected_value_improvement', 0)
                report += f"{i+1}. {scenario}: {override['action']} (+{improvement:.4f} EV)\n"
        
        report += f"\nTraining completed successfully!"
        
        return report
