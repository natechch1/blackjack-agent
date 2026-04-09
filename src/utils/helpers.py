"""
Utility functions for Blackjack AI Agent.
"""
import os
import json
import yaml
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


def ensure_directories():
    """Ensure all necessary directories exist"""
    directories = [
        "data",
        "data/logs",
        "data/game_logs",
        "data/training",
        "models",
        "config"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


def save_game_session(session_data: Dict[str, Any], filename: Optional[str] = None) -> str:
    """Save game session data to CSV and JSON"""
    ensure_directories()
    
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"session_{timestamp}"
    
    # Save detailed JSON
    json_file = f"data/game_logs/{filename}.json"
    with open(json_file, 'w') as f:
        json.dump(session_data, f, indent=2, default=str)
    
    # Save CSV summary
    if session_data.get('detailed_hands'):
        hands_data = []
        for hand in session_data['detailed_hands']:
            hands_data.append({
                'round': hand.get('round', 0),
                'bet': hand.get('initial_bet', 0),
                'player_cards': ', '.join(hand.get('player_cards', [])),
                'dealer_upcard': hand.get('dealer_upcard', ''),
                'true_count': hand.get('true_count', 0),
                'net_result': hand.get('net_result', 0),
                'bankroll_after': hand.get('bankroll_after', 0)
            })
        
        df = pd.DataFrame(hands_data)
        csv_file = f"data/game_logs/{filename}.csv"
        df.to_csv(csv_file, index=False)
        
        return json_file
    
    return json_file


def load_game_session(filename: str) -> Optional[Dict[str, Any]]:
    """Load game session data from file"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def export_strategy_table(basic_strategy, filename: Optional[str] = None) -> str:
    """Export basic strategy table to file"""
    ensure_directories()
    
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"models/basic_strategy_{timestamp}.json"
    
    basic_strategy.export_tables(filename)
    return filename


def calculate_session_stats(game_log: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate comprehensive session statistics"""
    if not game_log:
        return {}
    
    # Basic counts
    total_hands = len(game_log)
    wins = sum(1 for hand in game_log if hand.get('net_result', 0) > 0)
    losses = sum(1 for hand in game_log if hand.get('net_result', 0) < 0)
    pushes = total_hands - wins - losses
    
    # Financial metrics
    total_wagered = sum(hand.get('initial_bet', 0) for hand in game_log)
    total_profit = sum(hand.get('net_result', 0) for hand in game_log)
    
    # Betting analysis
    avg_bet = total_wagered / total_hands if total_hands > 0 else 0
    max_bet = max((hand.get('initial_bet', 0) for hand in game_log), default=0)
    min_bet = min((hand.get('initial_bet', 0) for hand in game_log), default=0)
    
    # Count analysis
    true_counts = [hand.get('true_count', 0) for hand in game_log]
    avg_true_count = sum(true_counts) / len(true_counts) if true_counts else 0
    max_true_count = max(true_counts) if true_counts else 0
    min_true_count = min(true_counts) if true_counts else 0
    
    # Count-based performance
    positive_count_hands = [hand for hand in game_log if hand.get('true_count', 0) > 1]
    positive_count_profit = sum(hand.get('net_result', 0) for hand in positive_count_hands)
    
    negative_count_hands = [hand for hand in game_log if hand.get('true_count', 0) < -1]
    negative_count_profit = sum(hand.get('net_result', 0) for hand in negative_count_hands)
    
    return {
        'total_hands': total_hands,
        'wins': wins,
        'losses': losses,
        'pushes': pushes,
        'win_rate': wins / total_hands if total_hands > 0 else 0,
        'total_wagered': total_wagered,
        'total_profit': total_profit,
        'roi': total_profit / total_wagered if total_wagered > 0 else 0,
        'avg_bet': avg_bet,
        'max_bet': max_bet,
        'min_bet': min_bet,
        'avg_true_count': avg_true_count,
        'max_true_count': max_true_count,
        'min_true_count': min_true_count,
        'positive_count_hands': len(positive_count_hands),
        'positive_count_profit': positive_count_profit,
        'negative_count_hands': len(negative_count_hands),
        'negative_count_profit': negative_count_profit,
        'positive_count_roi': (
            positive_count_profit / sum(h.get('initial_bet', 0) for h in positive_count_hands)
            if positive_count_hands else 0
        ),
        'negative_count_roi': (
            negative_count_profit / sum(h.get('initial_bet', 0) for h in negative_count_hands) 
            if negative_count_hands else 0
        )
    }


def format_currency(amount: float) -> str:
    """Format currency with appropriate signs and precision"""
    if amount >= 0:
        return f"${amount:,.2f}"
    else:
        return f"-${abs(amount):,.2f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format percentage with sign"""
    return f"{value * 100:+.{decimals}f}%"


def create_performance_report(session_data: Dict[str, Any]) -> str:
    """Create a formatted performance report"""
    if not session_data.get('detailed_hands'):
        return "No session data available"
    
    stats = calculate_session_stats(session_data['detailed_hands'])
    
    report = f"""
BLACKJACK AI PERFORMANCE REPORT
{'='*50}

Session Overview:
- Date: {session_data.get('session_start', 'N/A')}
- Duration: {session_data.get('session_end', 'N/A')}
- Hands Played: {stats['total_hands']:,}

Financial Performance:
- Total Wagered: {format_currency(stats['total_wagered'])}
- Net Profit: {format_currency(stats['total_profit'])}
- ROI: {format_percentage(stats['roi'])}
- Average Bet: {format_currency(stats['avg_bet'])}

Win/Loss Record:
- Wins: {stats['wins']} ({format_percentage(stats['wins']/stats['total_hands'])})
- Losses: {stats['losses']} ({format_percentage(stats['losses']/stats['total_hands'])})
- Pushes: {stats['pushes']} ({format_percentage(stats['pushes']/stats['total_hands'])})

Card Counting Analysis:
- Average True Count: {stats['avg_true_count']:.2f}
- Max True Count: {stats['max_true_count']:.1f}
- Min True Count: {stats['min_true_count']:.1f}

Count-Based Performance:
- Positive Count Hands: {stats['positive_count_hands']} 
- Positive Count Profit: {format_currency(stats['positive_count_profit'])}
- Positive Count ROI: {format_percentage(stats['positive_count_roi'])}

- Negative Count Hands: {stats['negative_count_hands']}
- Negative Count Profit: {format_currency(stats['negative_count_profit'])}
- Negative Count ROI: {format_percentage(stats['negative_count_roi'])}

Bankroll Information:
- Initial Bankroll: {format_currency(session_data.get('final_state', {}).get('initial_bankroll', 0))}
- Final Bankroll: {format_currency(session_data.get('final_state', {}).get('current_bankroll', 0))}
- Peak Bankroll: {format_currency(session_data.get('final_state', {}).get('peak_bankroll', 0))}
- Max Drawdown: {format_percentage(session_data.get('final_state', {}).get('max_drawdown', 0))}

{'='*50}
"""
    
    return report


def validate_config(config: Dict[str, Any]) -> List[str]:
    """Validate configuration and return list of issues"""
    issues = []
    
    # Check LLM config
    if 'llm' not in config:
        issues.append("Missing 'llm' configuration")
    else:
        llm_config = config['llm']
        if 'model' not in llm_config:
            issues.append("Missing 'llm.model' configuration")
        if llm_config.get('temperature', 0.1) < 0 or llm_config.get('temperature', 0.1) > 2:
            issues.append("LLM temperature should be between 0 and 2")
    
    # Check game config
    if 'game' not in config:
        issues.append("Missing 'game' configuration")
    else:
        game_config = config['game']
        if game_config.get('num_decks', 6) < 1 or game_config.get('num_decks', 6) > 8:
            issues.append("Number of decks should be between 1 and 8")
        if game_config.get('penetration', 0.75) < 0.5 or game_config.get('penetration', 0.75) > 0.9:
            issues.append("Penetration should be between 0.5 and 0.9")
    
    # Check bankroll config
    if 'bankroll' not in config:
        issues.append("Missing 'bankroll' configuration")
    else:
        bankroll_config = config['bankroll']
        if bankroll_config.get('initial_bankroll', 10000) < 1000:
            issues.append("Initial bankroll should be at least $1000")
        if bankroll_config.get('base_bet', 25) < 5:
            issues.append("Base bet should be at least $5")
        
        initial = bankroll_config.get('initial_bankroll', 10000)
        base_bet = bankroll_config.get('base_bet', 25)
        if initial / base_bet < 40:
            issues.append("Bankroll should be at least 40x base bet for safety")
    
    return issues


def check_system_requirements() -> Dict[str, bool]:
    """Check system requirements and dependencies"""
    requirements = {}
    
    # Check Ollama
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        requirements['ollama'] = response.status_code == 200
    except:
        requirements['ollama'] = False
    
    # Check Python packages
    required_packages = [
        'langchain', 'langchain_community', 'ollama',
        'pandas', 'numpy', 'streamlit', 'plotly',
        'yaml', 'requests'
    ]
    
    for package in required_packages:
        try:
            __import__(package)
            requirements[f'package_{package}'] = True
        except ImportError:
            requirements[f'package_{package}'] = False
    
    # Check directories
    requirements['data_directory'] = os.path.exists('data')
    requirements['models_directory'] = os.path.exists('models')
    requirements['config_directory'] = os.path.exists('config')
    
    return requirements


def setup_logging(log_level: str = "INFO") -> None:
    """Setup logging configuration"""
    import logging
    from datetime import datetime
    
    ensure_directories()
    
    # Create log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = f"data/logs/blackjack_agent_{timestamp}.log"
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized - Log file: {log_file}")


def get_latest_session_file(pattern: str = "session_*.json") -> Optional[str]:
    """Get the most recent session file"""
    files = list(Path("data/game_logs").glob(pattern))
    if not files:
        return None
    
    latest = max(files, key=os.path.getctime)
    return str(latest)


def cleanup_old_files(directory: str, days_old: int = 30):
    """Clean up files older than specified days"""
    from datetime import datetime, timedelta
    
    cutoff_date = datetime.now() - timedelta(days=days_old)
    directory_path = Path(directory)
    
    if not directory_path.exists():
        return
    
    deleted_count = 0
    for file_path in directory_path.iterdir():
        if file_path.is_file():
            file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            if file_time < cutoff_date:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except OSError:
                    pass  # Skip files that can't be deleted
    
    print(f"Cleaned up {deleted_count} old files from {directory}")


class ConfigManager:
    """Configuration management utilities"""
    
    @staticmethod
    def create_default_config(filename: str = "config/config.yaml"):
        """Create a default configuration file"""
        ensure_directories()
        
        default_config = {
            'llm': {
                'model': 'deepseek-r1:1.5b',
                'base_url': 'http://localhost:11434',
                'temperature': 0.1,
                'max_tokens': 2048,
                'timeout': 120
            },
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
            'counting': {
                'system': 'hi_lo',
                'true_count_divisor': 'decks_remaining',
                'betting_correlation': 0.97,
                'playing_efficiency': 0.51
            },
            'bankroll': {
                'initial_bankroll': 10000,
                'base_bet': 25,
                'kelly_fraction': 0.25,
                'max_bet_multiplier': 8,
                'stop_loss_pct': 0.5,
                'stop_win_pct': 2.0
            },
            'training': {
                'self_play_episodes': 50000,
                'optimization_rounds': 10,
                'threshold_search_grid': 0.1,
                'epsilon_greedy': 0.1,
                'learning_rate': 0.01,
                'batch_size': 1000
            },
            'strategy': {
                'use_overrides': True,
                'overrides_file': 'models/overrides.json',
                'basic_strategy_file': 'models/basic_strategy.json'
            },
            'logging': {
                'level': 'INFO',
                'file': 'data/logs/blackjack_agent.log',
                'csv_output': 'data/game_logs/session_{timestamp}.csv',
                'max_file_size': '50MB',
                'backup_count': 5
            },
            'simulation': {
                'monte_carlo_iterations': 10000,
                'parallel_processes': 4,
                'confidence_level': 0.95
            },
            'ui': {
                'title': 'Blackjack AI Agent Dashboard',
                'refresh_interval': 5,
                'chart_max_points': 1000,
                'show_debugging': False
            }
        }
        
        with open(filename, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)
        
        return filename
    
    @staticmethod
    def merge_configs(default_config: Dict, user_config: Dict) -> Dict:
        """Merge user config with defaults"""
        merged = default_config.copy()
        
        def deep_merge(base: Dict, override: Dict):
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
        
        deep_merge(merged, user_config)
        return merged
