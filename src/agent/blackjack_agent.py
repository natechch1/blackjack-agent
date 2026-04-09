"""
Blackjack AI Agent powered by Ollama and LangChain.
"""
import json
import yaml
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from langchain_ollama import OllamaLLM
from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.schema import BaseOutputParser
from langchain_community.llms import Ollama  # Keep for fallback
from langchain.memory import ConversationBufferWindowMemory
import warnings

from ..game.blackjack_env import BlackjackEnvironment, Action, GameResult
from ..game.cards import Hand, Card
from ..tools.basic_strategy import BasicStrategy
from ..tools.card_counting import CardCounter, CountInfo
from ..tools.monte_carlo import MonteCarloSimulator
from ..tools.money_management import BankrollManager, RiskLevel, BetRecommendation


@dataclass
class AgentDecision:
    """Agent's decision with reasoning"""
    action: Action
    reasoning: str
    confidence: float
    tool_recommendations: Dict[str, Any]
    expected_value: Optional[float] = None
    risk_assessment: Optional[str] = None


class BlackjackAgent:
    """Intelligent Blackjack agent with tool access"""
    
    def __init__(
        self, 
        model: str = "deepseek-r1:1.5b",
        config_path: Optional[str] = None,
        ollama_base_url: str = "http://localhost:11434"
    ):
        self.config = self._load_config(config_path)
        
        # Initialize LLM
        self.llm = OllamaLLM(
            model=model,
            base_url=ollama_base_url,
            temperature=self.config['llm']['temperature']
        )
        
        # Initialize game environment
        self.env = BlackjackEnvironment(config_path)
        
        # Initialize tools
        self.basic_strategy = BasicStrategy(
            overrides_file=self.config['strategy'].get('overrides_file')
        )
        self.card_counter = CardCounter()
        self.monte_carlo = MonteCarloSimulator()
        self.bankroll_manager = BankrollManager(
            initial_bankroll=self.config['bankroll']['initial_bankroll'],
            base_bet=self.config['bankroll']['base_bet'],
            risk_level=RiskLevel.MODERATE
        )
        
        # Initialize agent
        self.tools = self._create_tools()
        
        # Suppress memory deprecation warning temporarily
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*migration guide.*", category=DeprecationWarning)
            self.memory = ConversationBufferWindowMemory(
                k=10, 
                return_messages=True,
                memory_key="chat_history"
            )
        self.agent = self._create_agent()
        
        # Game state
        self.game_log = []
        self.current_session_hands = 0
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration"""
        if config_path is None:
            config_path = "config/config.yaml"
        
        try:
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            # Return minimal default config
            return {
                'llm': {'temperature': 0.1, 'max_tokens': 2048},
                'bankroll': {'initial_bankroll': 10000, 'base_bet': 25},
                'strategy': {},
                'game': {}
            }
    
    def _create_tools(self) -> List[Tool]:
        """Create tools for the agent"""
        
        tools = [
            Tool(
                name="basic_strategy_advisor",
                description="Get basic strategy recommendation for current hand",
                func=self._basic_strategy_tool
            ),
            Tool(
                name="card_counting_info",
                description="Get current card count and true count information",
                func=self._card_counting_tool
            ),
            Tool(
                name="monte_carlo_simulation",
                description="Run Monte Carlo simulation for hand outcome probabilities",
                func=self._monte_carlo_tool
            ),
            Tool(
                name="betting_advisor",
                description="Get betting size recommendation based on count and bankroll",
                func=self._betting_tool
            ),
            Tool(
                name="risk_assessor",
                description="Assess current risk and bankroll status",
                func=self._risk_assessment_tool
            ),
            Tool(
                name="game_state_analyzer",
                description="Analyze current game state and situation",
                func=self._game_state_tool
            )
        ]
        
        return tools
    
    def _basic_strategy_tool(self, query: str) -> str:
        """Basic strategy consultation tool"""
        try:
            game_state = self.env.game_state
            if not game_state.current_hand or not game_state.dealer_hand.cards:
                return "No active hand to analyze"
            
            current_hand = game_state.current_hand
            dealer_upcard = self.env.get_dealer_upcard()
            available_actions = self.env.get_valid_actions()
            
            action, explanation, confidence = self.basic_strategy.get_recommendation(
                current_hand, dealer_upcard, available_actions
            )
            
            # Check for count-based deviations
            true_count = self.env.shoe.true_count if self.env.shoe else 0
            deviation = self.basic_strategy.get_deviation_recommendation(
                current_hand, dealer_upcard, true_count
            )
            
            result = {
                "basic_strategy_action": action.value,
                "explanation": explanation,
                "confidence": confidence,
                "available_actions": [a.value for a in available_actions]
            }
            
            if deviation and deviation[0]:
                result["count_deviation"] = {
                    "action": deviation[0].value,
                    "reason": deviation[1]
                }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return f"Error in basic strategy analysis: {str(e)}"
    
    def _card_counting_tool(self, query: str) -> str:
        """Card counting information tool"""
        try:
            if not self.env.shoe:
                return "No shoe information available"
            
            count_info = self.card_counter.get_count_info(self.env.shoe)
            
            # Get betting recommendation
            bet_rec = self.card_counter.get_betting_recommendation(
                count_info.true_count,
                self.bankroll_manager.base_bet,
                self.bankroll_manager.current_bankroll
            )
            
            # Risk assessment
            risk = self.card_counter.get_risk_assessment(
                count_info.true_count,
                self.bankroll_manager.current_bankroll
            )
            
            result = {
                "running_count": count_info.running_count,
                "true_count": round(count_info.true_count, 2),
                "cards_remaining": self.env.shoe.cards_remaining,
                "decks_remaining": round(count_info.decks_remaining, 1),
                "recommended_bet": bet_rec[0],
                "betting_explanation": bet_rec[1],
                "risk_assessment": risk,
                "counting_system": "Hi-Lo",
                "betting_correlation": count_info.betting_correlation,
                "playing_efficiency": count_info.playing_efficiency
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return f"Error in card counting analysis: {str(e)}"
    
    def _monte_carlo_tool(self, query: str) -> str:
        """Monte Carlo simulation tool"""
        try:
            game_state = self.env.game_state
            if not game_state.current_hand or not game_state.dealer_hand.cards:
                return "No active hand to simulate"
            
            current_hand = game_state.current_hand
            dealer_upcard = self.env.get_dealer_upcard()
            available_actions = self.env.get_valid_actions()
            
            # Simulate different actions
            results = {}
            
            for action in available_actions[:3]:  # Limit to avoid timeout
                sim_result = self.monte_carlo.simulate_hand_outcome(
                    current_hand.cards,
                    dealer_upcard,
                    num_simulations=1000,  # Reduced for speed
                    action=action
                )
                
                results[action.value] = {
                    "win_probability": round(sim_result.win_probability, 3),
                    "expected_value": round(sim_result.expected_value, 3),
                    "confidence_interval": [
                        round(sim_result.confidence_interval[0], 3),
                        round(sim_result.confidence_interval[1], 3)
                    ]
                }
            
            # Find best action
            best_action = max(
                results.keys(),
                key=lambda a: results[a]["expected_value"]
            )
            
            return json.dumps({
                "simulation_results": results,
                "recommended_action": best_action,
                "simulations_run": 1000,
                "best_expected_value": results[best_action]["expected_value"]
            }, indent=2)
            
        except Exception as e:
            return f"Error in Monte Carlo simulation: {str(e)}"
    
    def _betting_tool(self, query: str) -> str:
        """Betting advisor tool"""
        try:
            if not self.env.shoe:
                return "No count information available"
            
            true_count = self.env.shoe.true_count
            bet_recommendation = self.bankroll_manager.get_count_based_bet(true_count)
            
            bankroll_state = self.bankroll_manager.get_bankroll_state()
            
            result = {
                "recommended_bet": bet_recommendation.bet_amount,
                "bet_multiplier": round(bet_recommendation.bet_multiplier, 1),
                "reasoning": bet_recommendation.reasoning,
                "risk_level": bet_recommendation.risk_level,
                "kelly_fraction": round(bet_recommendation.kelly_fraction, 3),
                "current_bankroll": bankroll_state.current_bankroll,
                "base_bet": self.bankroll_manager.base_bet,
                "max_loss_potential": bet_recommendation.max_loss_potential
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return f"Error in betting analysis: {str(e)}"
    
    def _risk_assessment_tool(self, query: str) -> str:
        """Risk assessment tool"""
        try:
            bankroll_state = self.bankroll_manager.get_bankroll_state()
            risk_metrics = self.bankroll_manager.get_risk_metrics()
            should_stop, stop_reason = self.bankroll_manager.should_stop_session()
            
            result = {
                "current_bankroll": bankroll_state.current_bankroll,
                "profit_loss": bankroll_state.net_profit,
                "roi": round(bankroll_state.roi * 100, 2),
                "current_drawdown_pct": round(bankroll_state.current_drawdown * 100, 1),
                "max_drawdown_pct": round(bankroll_state.max_drawdown * 100, 1),
                "win_rate": round(bankroll_state.win_rate * 100, 1),
                "hands_played": bankroll_state.total_hands,
                "should_stop_session": should_stop,
                "stop_reason": stop_reason,
                "risk_metrics": risk_metrics
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return f"Error in risk assessment: {str(e)}"
    
    def _game_state_tool(self, query: str) -> str:
        """Game state analysis tool"""
        try:
            game_state = self.env.game_state
            
            result = {
                "round_number": game_state.round_number,
                "player_hands": [],
                "dealer_upcard": None,
                "valid_actions": [],
                "game_summary": self.env.get_game_summary()
            }
            
            # Player hands info
            for i, hand in enumerate(game_state.player_hands):
                hand_info = {
                    "hand_index": i,
                    "cards": [str(card) for card in hand.cards],
                    "value": hand.value,
                    "is_soft": hand.is_soft,
                    "is_pair": hand.is_pair,
                    "can_split": hand.can_split,
                    "can_double": hand.can_double,
                    "bet": hand.bet,
                    "is_current": i == game_state.current_hand_index
                }
                result["player_hands"].append(hand_info)
            
            # Dealer info
            if game_state.dealer_hand.cards:
                dealer_upcard = self.env.get_dealer_upcard()
                if dealer_upcard:
                    result["dealer_upcard"] = str(dealer_upcard)
            
            # Valid actions
            result["valid_actions"] = [
                action.value for action in self.env.get_valid_actions()
            ]
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return f"Error in game state analysis: {str(e)}"
    
    def _create_agent(self) -> AgentExecutor:
        """Create the LangChain agent"""
        
        prompt_template = """
You are an expert Blackjack AI agent with access to professional tools. 
Your goal is to make optimal decisions to maximize long-term profit while managing risk.

Available tools:
{tool_names}
{tools}

When making decisions, consider:
1. Basic strategy recommendations
2. Card counting information (Hi-Lo system)
3. Monte Carlo simulation results
4. Bankroll management principles
5. Risk assessment

Current situation: {input}

Your reasoning process:
{agent_scratchpad}

Always provide:
1. Your recommended action
2. Clear reasoning
3. Confidence level (1-10)
4. Risk assessment

Think step by step and use the tools to gather information before making decisions.
"""
        
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["input", "tools", "tool_names", "agent_scratchpad"]
        )
        
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            max_iterations=3,
            handle_parsing_errors=True
        )
    
    def make_decision(self, hand_index: int = 0) -> AgentDecision:
        """Make a decision for the current hand using AI reasoning"""
        
        try:
            # Prepare context
            game_summary = self.env.get_game_summary()
            hand_description = self.env.get_hand_description(hand_index)
            valid_actions = self.env.get_valid_actions(hand_index)
            
            # If no valid actions, return None (should be auto-handled)
            if not valid_actions:
                return AgentDecision(
                    action=None,
                    reasoning="No valid actions available - hand should be auto-resolved",
                    confidence=10.0,
                    tool_recommendations={}
                )
            
            # Create input for agent
            input_text = f"""
            Game Situation:
            {game_summary}
            
            Current Hand: {hand_description}
            Valid Actions: {[action.value for action in valid_actions]}
            
            Please analyze this situation and recommend the best action.
            Consider basic strategy, card counting, expected value, and risk management.
            """
            
            # Get agent response
            response = self.agent.invoke({"input": input_text})
            
            # Parse agent output to extract action
            action = self._parse_agent_action(response["output"], valid_actions)
            
            return AgentDecision(
                action=action,
                reasoning=response["output"],
                confidence=8.0,  # Default confidence
                tool_recommendations={}
            )
            
        except Exception as e:
            # Fallback to basic strategy
            current_hand = self.env.game_state.player_hands[hand_index]
            dealer_upcard = self.env.get_dealer_upcard()
            
            action, explanation, confidence = self.basic_strategy.get_recommendation(
                current_hand, dealer_upcard, valid_actions
            )
            
            return AgentDecision(
                action=action,
                reasoning=f"Fallback to basic strategy: {explanation} (Error: {str(e)})",
                confidence=confidence * 10,  # Convert to 1-10 scale
                tool_recommendations={}
            )
    
    def _parse_agent_action(self, agent_output: str, valid_actions: List[Action]) -> Action:
        """Parse the agent's output to extract the recommended action"""
        
        output_lower = agent_output.lower()
        
        # Look for action keywords in order of priority
        action_keywords = {
            'split': Action.SPLIT,
            'double': Action.DOUBLE,
            'surrender': Action.SURRENDER,
            'hit': Action.HIT,
            'stand': Action.STAND
        }
        
        for keyword, action in action_keywords.items():
            if keyword in output_lower and action in valid_actions:
                return action
        
        # Default to most conservative action available
        if Action.STAND in valid_actions:
            return Action.STAND
        elif Action.HIT in valid_actions:
            return Action.HIT
        else:
            return valid_actions[0] if valid_actions else Action.STAND
    
    def get_bet_size(self, round_number: int) -> float:
        """Determine bet size for next hand"""
        if self.env.shoe:
            bet_recommendation = self.bankroll_manager.get_count_based_bet(
                self.env.shoe.true_count
            )
            return bet_recommendation.bet_amount
        else:
            return self.bankroll_manager.base_bet
    
    def play_hand(self) -> Dict[str, Any]:
        """Play a complete hand of Blackjack"""
        
        # Get bet size
        bet_size = self.get_bet_size(self.env.game_state.round_number + 1)
        
        # Start new round
        self.env.start_new_round(bet_size)
        
        # Log initial state
        hand_log = {
            'round': self.env.game_state.round_number,
            'initial_bet': bet_size,
            'player_cards': [str(card) for card in self.env.game_state.player_hands[0].cards],
            'dealer_upcard': str(self.env.get_dealer_upcard()) if self.env.get_dealer_upcard() else None,
            'true_count': self.env.shoe.true_count if self.env.shoe else 0,
            'bankroll_before': self.bankroll_manager.current_bankroll,
            'decisions': []
        }
        
        # Play each hand
        while not self.env.game_state.is_game_over:
            hand_index = self.env.game_state.current_hand_index
            
            # Check if current hand needs a decision
            valid_actions = self.env.get_valid_actions(hand_index)
            if not valid_actions:
                # Hand is auto-resolved (blackjack, busted, etc.), move to next
                self.env._move_to_next_hand()
                continue
            
            # Make decision
            decision = self.make_decision(hand_index)
            
            # If no action needed (shouldn't happen with the check above), skip
            if decision.action is None:
                self.env._move_to_next_hand()
                continue
            
            # Log decision
            hand_log['decisions'].append({
                'hand_index': hand_index,
                'action': decision.action.value,
                'reasoning': decision.reasoning,
                'confidence': decision.confidence
            })
            
            # Execute action
            self.env.take_action(decision.action, hand_index)
        
        # Play dealer
        self.env.play_dealer()
        
        # Calculate results
        results = self.env.calculate_results()
        
        # Update bankroll
        total_result = sum(payout for _, payout in results)
        net_result = total_result - bet_size  # Net profit/loss
        
        self.bankroll_manager.update_bankroll(net_result, bet_size)
        
        # Complete hand log
        hand_log.update({
            'results': [(result.value, payout) for result, payout in results],
            'net_result': net_result,
            'bankroll_after': self.bankroll_manager.current_bankroll,
            'dealer_final': [str(card) for card in self.env.game_state.dealer_hand.cards],
            'dealer_value': self.env.game_state.dealer_hand.value
        })
        
        # Add to game log
        self.game_log.append(hand_log)
        self.current_session_hands += 1
        
        return hand_log
    
    def play_session(self, num_hands: int = 100) -> Dict[str, Any]:
        """Play a session of multiple hands"""
        
        session_start = datetime.now()
        session_hands = []
        
        for hand_num in range(num_hands):
            # Check if should stop
            should_stop, reason = self.bankroll_manager.should_stop_session()
            if should_stop:
                break
            
            # Play hand
            hand_result = self.play_hand()
            session_hands.append(hand_result)
            
            # Check for shoe reshuffle
            if self.env.shoe.needs_shuffle():
                self.card_counter.reset_count(self.env.shoe.num_decks)
        
        # Session summary
        session_summary = {
            'session_start': session_start.isoformat(),
            'session_end': datetime.now().isoformat(),
            'hands_played': len(session_hands),
            'hands_requested': num_hands,
            'bankroll_summary': self.bankroll_manager.get_session_summary(),
            'final_state': self.bankroll_manager.get_bankroll_state(),
            'detailed_hands': session_hands
        }
        
        return session_summary
