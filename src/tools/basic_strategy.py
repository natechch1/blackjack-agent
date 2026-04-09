"""
Basic strategy tables and recommendations for Blackjack.
"""
from typing import Dict, Any, Optional, Tuple
from enum import Enum
import json

from ..game.blackjack_env import Action
from ..game.cards import Hand, Card, Rank


class StrategyAction(Enum):
    """Strategy actions with abbreviations"""
    HIT = "H"
    STAND = "S"
    DOUBLE_OR_HIT = "Dh"  # Double if allowed, otherwise hit
    DOUBLE_OR_STAND = "Ds"  # Double if allowed, otherwise stand
    SPLIT = "P"
    SURRENDER_OR_HIT = "Rh"  # Surrender if allowed, otherwise hit
    SURRENDER_OR_STAND = "Rs"  # Surrender if allowed, otherwise stand
    SURRENDER_OR_SPLIT = "Rp"  # Surrender if allowed, otherwise split


class BasicStrategy:
    """Basic strategy implementation with hard, soft, and pair tables"""
    
    def __init__(self, overrides_file: Optional[str] = None):
        self.hard_table = self._build_hard_table()
        self.soft_table = self._build_soft_table()
        self.pair_table = self._build_pair_table()
        self.overrides = self._load_overrides(overrides_file)
    
    def _build_hard_table(self) -> Dict[Tuple[int, int], StrategyAction]:
        """Build hard hands strategy table"""
        # Hard hands table: (player_total, dealer_upcard) -> action
        table = {}
        
        # Hard 5-8: Always hit
        for player_total in range(5, 9):
            for dealer_card in range(2, 12):  # 2-10, A(11)
                table[(player_total, dealer_card)] = StrategyAction.HIT
        
        # Hard 9: Double against 3-6, otherwise hit
        for dealer_card in range(2, 12):
            if 3 <= dealer_card <= 6:
                table[(9, dealer_card)] = StrategyAction.DOUBLE_OR_HIT
            else:
                table[(9, dealer_card)] = StrategyAction.HIT
        
        # Hard 10: Double against 2-9, otherwise hit
        for dealer_card in range(2, 12):
            if 2 <= dealer_card <= 9:
                table[(10, dealer_card)] = StrategyAction.DOUBLE_OR_HIT
            else:
                table[(10, dealer_card)] = StrategyAction.HIT
        
        # Hard 11: Always double (or hit if can't double)
        for dealer_card in range(2, 12):
            table[(11, dealer_card)] = StrategyAction.DOUBLE_OR_HIT
        
        # Hard 12: Stand against 4-6, otherwise hit
        for dealer_card in range(2, 12):
            if 4 <= dealer_card <= 6:
                table[(12, dealer_card)] = StrategyAction.STAND
            else:
                table[(12, dealer_card)] = StrategyAction.HIT
        
        # Hard 13-16: Stand against 2-6, otherwise hit
        for player_total in range(13, 17):
            for dealer_card in range(2, 12):
                if 2 <= dealer_card <= 6:
                    table[(player_total, dealer_card)] = StrategyAction.STAND
                else:
                    table[(player_total, dealer_card)] = StrategyAction.HIT
        
        # Hard 16 vs 10: Consider surrender
        table[(16, 10)] = StrategyAction.SURRENDER_OR_HIT
        table[(16, 11)] = StrategyAction.SURRENDER_OR_HIT  # vs Ace
        
        # Hard 15 vs 10: Consider surrender
        table[(15, 10)] = StrategyAction.SURRENDER_OR_HIT
        
        # Hard 17-21: Always stand
        for player_total in range(17, 22):
            for dealer_card in range(2, 12):
                table[(player_total, dealer_card)] = StrategyAction.STAND
        
        return table
    
    def _build_soft_table(self) -> Dict[Tuple[int, int], StrategyAction]:
        """Build soft hands strategy table"""
        table = {}
        
        # Soft 13-15 (A,2 to A,4): Double against 5-6, otherwise hit
        for soft_total in range(13, 16):
            for dealer_card in range(2, 12):
                if 5 <= dealer_card <= 6:
                    table[(soft_total, dealer_card)] = StrategyAction.DOUBLE_OR_HIT
                else:
                    table[(soft_total, dealer_card)] = StrategyAction.HIT
        
        # Soft 16-17 (A,5 to A,6): Double against 4-6, otherwise hit
        for soft_total in range(16, 18):
            for dealer_card in range(2, 12):
                if 4 <= dealer_card <= 6:
                    table[(soft_total, dealer_card)] = StrategyAction.DOUBLE_OR_HIT
                else:
                    table[(soft_total, dealer_card)] = StrategyAction.HIT
        
        # Soft 18 (A,7): Complex strategy
        for dealer_card in range(2, 12):
            if dealer_card in [3, 4, 5, 6]:
                table[(18, dealer_card)] = StrategyAction.DOUBLE_OR_STAND
            elif dealer_card in [2, 7, 8]:
                table[(18, dealer_card)] = StrategyAction.STAND
            else:  # 9, 10, A
                table[(18, dealer_card)] = StrategyAction.HIT
        
        # Soft 19-21: Always stand
        for soft_total in range(19, 22):
            for dealer_card in range(2, 12):
                table[(soft_total, dealer_card)] = StrategyAction.STAND
        
        return table
    
    def _build_pair_table(self) -> Dict[Tuple[str, int], StrategyAction]:
        """Build pairs strategy table"""
        table = {}
        
        # Pair of Aces: Always split
        for dealer_card in range(2, 12):
            table[("A", dealer_card)] = StrategyAction.SPLIT
        
        # Pair of 2s or 3s: Split against 2-7, otherwise hit
        for pair_rank in ["2", "3"]:
            for dealer_card in range(2, 12):
                if 2 <= dealer_card <= 7:
                    table[(pair_rank, dealer_card)] = StrategyAction.SPLIT
                else:
                    table[(pair_rank, dealer_card)] = StrategyAction.HIT
        
        # Pair of 4s: Split against 5-6, otherwise hit
        for dealer_card in range(2, 12):
            if 5 <= dealer_card <= 6:
                table[("4", dealer_card)] = StrategyAction.SPLIT
            else:
                table[("4", dealer_card)] = StrategyAction.HIT
        
        # Pair of 5s: Never split, treat as hard 10
        for dealer_card in range(2, 12):
            if 2 <= dealer_card <= 9:
                table[("5", dealer_card)] = StrategyAction.DOUBLE_OR_HIT
            else:
                table[("5", dealer_card)] = StrategyAction.HIT
        
        # Pair of 6s: Split against 2-6, otherwise hit
        for dealer_card in range(2, 12):
            if 2 <= dealer_card <= 6:
                table[("6", dealer_card)] = StrategyAction.SPLIT
            else:
                table[("6", dealer_card)] = StrategyAction.HIT
        
        # Pair of 7s: Split against 2-7, otherwise hit
        for dealer_card in range(2, 12):
            if 2 <= dealer_card <= 7:
                table[("7", dealer_card)] = StrategyAction.SPLIT
            else:
                table[("7", dealer_card)] = StrategyAction.HIT
        
        # Pair of 8s: Always split
        for dealer_card in range(2, 12):
            table[("8", dealer_card)] = StrategyAction.SPLIT
        
        # Pair of 9s: Split against 2-9 except 7, stand against 7,10,A
        for dealer_card in range(2, 12):
            if dealer_card in [2, 3, 4, 5, 6, 8, 9]:
                table[("9", dealer_card)] = StrategyAction.SPLIT
            else:  # 7, 10, A
                table[("9", dealer_card)] = StrategyAction.STAND
        
        # Pair of 10s: Never split
        for dealer_card in range(2, 12):
            table[("10", dealer_card)] = StrategyAction.STAND
        
        return table
    
    def _load_overrides(self, overrides_file: Optional[str]) -> Dict[str, Any]:
        """Load strategy overrides from JSON file"""
        if not overrides_file:
            return {}
        
        try:
            with open(overrides_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def get_recommendation(
        self, 
        player_hand: Hand, 
        dealer_upcard: Card,
        available_actions: list
    ) -> Tuple[Action, str, float]:
        """
        Get strategy recommendation for given situation
        
        Returns:
            (action, explanation, confidence)
        """
        dealer_value = dealer_upcard.value if dealer_upcard.rank != Rank.ACE else 11
        
        # Check for overrides first
        override_key = self._get_override_key(player_hand, dealer_upcard)
        if override_key in self.overrides:
            action_str = self.overrides[override_key]["action"]
            explanation = f"Override: {self.overrides[override_key].get('reason', '')}"
            confidence = self.overrides[override_key].get("confidence", 1.0)
            action = self._string_to_action(action_str, available_actions)
            return action, explanation, confidence
        
        # Use basic strategy tables
        strategy_action, explanation = self._get_basic_strategy_action(
            player_hand, dealer_value
        )
        
        # Convert strategy action to actual action
        action = self._strategy_to_action(strategy_action, available_actions)
        
        return action, explanation, 0.95  # High confidence for basic strategy
    
    def _get_override_key(self, player_hand: Hand, dealer_upcard: Card) -> str:
        """Generate key for override lookup"""
        if player_hand.is_pair:
            pair_rank = player_hand.cards[0].rank.value
            return f"pair_{pair_rank}_vs_{dealer_upcard.rank.value}"
        elif player_hand.is_soft:
            return f"soft_{player_hand.value}_vs_{dealer_upcard.rank.value}"
        else:
            return f"hard_{player_hand.value}_vs_{dealer_upcard.rank.value}"
    
    def _get_basic_strategy_action(
        self, 
        player_hand: Hand, 
        dealer_value: int
    ) -> Tuple[StrategyAction, str]:
        """Get action from basic strategy tables"""
        
        if player_hand.is_pair and player_hand.can_split:
            # Use pair table
            pair_rank = player_hand.cards[0].rank.value
            if pair_rank in ["J", "Q", "K"]:
                pair_rank = "10"
            
            key = (pair_rank, dealer_value)
            if key in self.pair_table:
                action = self.pair_table[key]
                explanation = f"Pair of {pair_rank}s vs {dealer_value}: {action.value}"
                return action, explanation
        
        if player_hand.is_soft:
            # Use soft table
            key = (player_hand.value, dealer_value)
            if key in self.soft_table:
                action = self.soft_table[key]
                explanation = f"Soft {player_hand.value} vs {dealer_value}: {action.value}"
                return action, explanation
        
        # Use hard table
        key = (player_hand.value, dealer_value)
        if key in self.hard_table:
            action = self.hard_table[key]
            explanation = f"Hard {player_hand.value} vs {dealer_value}: {action.value}"
            return action, explanation
        
        # Fallback
        if player_hand.value < 17:
            return StrategyAction.HIT, f"Default: Hit on {player_hand.value}"
        else:
            return StrategyAction.STAND, f"Default: Stand on {player_hand.value}"
    
    def _strategy_to_action(
        self, 
        strategy_action: StrategyAction, 
        available_actions: list
    ) -> Action:
        """Convert strategy action to actual game action"""
        
        if strategy_action == StrategyAction.HIT:
            return Action.HIT
        elif strategy_action == StrategyAction.STAND:
            return Action.STAND
        elif strategy_action == StrategyAction.SPLIT:
            if Action.SPLIT in available_actions:
                return Action.SPLIT
            else:
                return Action.HIT  # Fallback if can't split
        elif strategy_action == StrategyAction.DOUBLE_OR_HIT:
            if Action.DOUBLE in available_actions:
                return Action.DOUBLE
            else:
                return Action.HIT
        elif strategy_action == StrategyAction.DOUBLE_OR_STAND:
            if Action.DOUBLE in available_actions:
                return Action.DOUBLE
            else:
                return Action.STAND
        elif strategy_action == StrategyAction.SURRENDER_OR_HIT:
            if Action.SURRENDER in available_actions:
                return Action.SURRENDER
            else:
                return Action.HIT
        elif strategy_action == StrategyAction.SURRENDER_OR_STAND:
            if Action.SURRENDER in available_actions:
                return Action.SURRENDER
            else:
                return Action.STAND
        elif strategy_action == StrategyAction.SURRENDER_OR_SPLIT:
            if Action.SURRENDER in available_actions:
                return Action.SURRENDER
            elif Action.SPLIT in available_actions:
                return Action.SPLIT
            else:
                return Action.HIT
        
        # Default fallback
        return Action.HIT
    
    def _string_to_action(self, action_str: str, available_actions: list) -> Action:
        """Convert string to Action enum"""
        action_map = {
            "hit": Action.HIT,
            "stand": Action.STAND,
            "double": Action.DOUBLE,
            "split": Action.SPLIT,
            "surrender": Action.SURRENDER
        }
        
        action = action_map.get(action_str.lower(), Action.HIT)
        
        # Check if action is available
        if action in available_actions:
            return action
        
        # Fallback logic
        if action == Action.DOUBLE:
            return Action.HIT if Action.HIT in available_actions else Action.STAND
        elif action == Action.SPLIT:
            return Action.HIT if Action.HIT in available_actions else Action.STAND
        elif action == Action.SURRENDER:
            return Action.HIT if Action.HIT in available_actions else Action.STAND
        
        return Action.HIT if Action.HIT in available_actions else Action.STAND
    
    def export_tables(self, filepath: str):
        """Export strategy tables to JSON file"""
        data = {
            "hard_hands": {f"{k[0]}_vs_{k[1]}": v.value for k, v in self.hard_table.items()},
            "soft_hands": {f"{k[0]}_vs_{k[1]}": v.value for k, v in self.soft_table.items()},
            "pairs": {f"{k[0]}_vs_{k[1]}": v.value for k, v in self.pair_table.items()}
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_deviation_recommendation(
        self, 
        player_hand: Hand, 
        dealer_upcard: Card, 
        true_count: float
    ) -> Optional[Tuple[Action, str]]:
        """
        Get count-based deviations from basic strategy
        Common indices for Hi-Lo system
        """
        dealer_value = dealer_upcard.value if dealer_upcard.rank != Rank.ACE else 11
        
        # Insurance bet (not implemented in this game but for completeness)
        if dealer_upcard.rank == Rank.ACE and true_count >= 3:
            return None, "Take insurance at TC +3 or higher"
        
        # 16 vs 10: Stand at TC >= 0
        if (player_hand.value == 16 and dealer_value == 10 and 
            not player_hand.is_pair and true_count >= 0):
            return Action.STAND, f"16 vs 10: Stand at TC {true_count:.1f}"
        
        # 15 vs 10: Stand at TC >= +4
        if (player_hand.value == 15 and dealer_value == 10 and 
            true_count >= 4):
            return Action.STAND, f"15 vs 10: Stand at TC {true_count:.1f}"
        
        # 10 vs 10: Double at TC >= +4
        if (player_hand.value == 10 and dealer_value == 10 and 
            true_count >= 4):
            return Action.DOUBLE, f"10 vs 10: Double at TC {true_count:.1f}"
        
        # 12 vs 3: Stand at TC >= +2
        if (player_hand.value == 12 and dealer_value == 3 and 
            true_count >= 2):
            return Action.STAND, f"12 vs 3: Stand at TC {true_count:.1f}"
        
        # 12 vs 2: Stand at TC >= +3
        if (player_hand.value == 12 and dealer_value == 2 and 
            true_count >= 3):
            return Action.STAND, f"12 vs 2: Stand at TC {true_count:.1f}"
        
        # 13 vs 2: Stand at TC >= -1
        if (player_hand.value == 13 and dealer_value == 2 and 
            true_count >= -1):
            return Action.STAND, f"13 vs 2: Stand at TC {true_count:.1f}"
        
        return None
