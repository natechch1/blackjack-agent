"""
Main entry point for Blackjack AI Agent.
"""
import argparse
import sys
import os
from pathlib import Path
import yaml
from datetime import datetime

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent))

from agent.blackjack_agent import BlackjackAgent
from training.self_play import SelfPlayTrainer
from ui.dashboard import main as run_dashboard


def load_config(config_path: str = "config/config.yaml") -> dict:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Config file {config_path} not found. Using defaults.")
        return {}


def setup_directories():
    """Create necessary directories"""
    directories = [
        "data/logs",
        "data/game_logs", 
        "data/training",
        "models"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {directory}")


def play_interactive_session():
    """Play an interactive Blackjack session"""
    print("\n🃏 Starting Interactive Blackjack Session")
    print("=" * 50)
    
    # Initialize agent
    config = load_config()
    model = config.get('llm', {}).get('model', 'deepseek-r1:1.5b')
    
    try:
        agent = BlackjackAgent(model=model)
        print(f"✓ Agent initialized with model: {model}")
        print(f"✓ Initial bankroll: ${agent.bankroll_manager.current_bankroll:,.2f}")
        print(f"✓ Base bet: ${agent.bankroll_manager.base_bet}")
        
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        print("Make sure Ollama is running and the model is available.")
        return
    
    # Interactive loop
    while True:
        print(f"\n--- Round {agent.env.game_state.round_number + 1} ---")
        print(f"Bankroll: ${agent.bankroll_manager.current_bankroll:,.2f}")
        
        # Check if should continue
        should_stop, reason = agent.bankroll_manager.should_stop_session()
        if should_stop:
            print(f"Session ended: {reason}")
            break
        
        # Show menu
        print("\nOptions:")
        print("1. Play single hand")
        print("2. Play 10 hands")
        print("3. Play 100 hands")
        print("4. Show bankroll status")
        print("5. Show recent hands")
        print("6. Exit")
        
        try:
            choice = input("\nEnter choice (1-6): ").strip()
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        
        if choice == '1':
            play_single_hand(agent)
        elif choice == '2':
            play_multiple_hands(agent, 10)
        elif choice == '3':
            play_multiple_hands(agent, 100)
        elif choice == '4':
            show_bankroll_status(agent)
        elif choice == '5':
            show_recent_hands(agent)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")
    
    # Session summary
    show_session_summary(agent)


def play_single_hand(agent: BlackjackAgent):
    """Play a single hand and show result"""
    try:
        result = agent.play_hand()
        
        print(f"\n🎲 Hand {result['round']} Result:")
        print(f"  Bet: ${result['initial_bet']}")
        print(f"  Player: {', '.join(result['player_cards'])}")
        print(f"  Dealer: {result['dealer_upcard']} + {result['dealer_final'][1:]}")
        print(f"  True Count: {result['true_count']:.1f}")
        print(f"  Net Result: ${result['net_result']:+.2f}")
        print(f"  New Bankroll: ${result['bankroll_after']:,.2f}")
        
        # Show decisions
        if result['decisions']:
            print("  Decisions:")
            for decision in result['decisions']:
                print(f"    {decision['action'].title()} (confidence: {decision['confidence']:.1f}/10)")
        
    except Exception as e:
        print(f"❌ Error playing hand: {e}")


def play_multiple_hands(agent: BlackjackAgent, num_hands: int):
    """Play multiple hands with progress"""
    print(f"\n🎲 Playing {num_hands} hands...")
    
    initial_bankroll = agent.bankroll_manager.current_bankroll
    
    try:
        session_result = agent.play_session(num_hands)
        
        final_bankroll = session_result['final_state'].current_bankroll
        profit = final_bankroll - initial_bankroll
        
        print(f"✓ Session completed!")
        print(f"  Hands played: {session_result['hands_played']}")
        print(f"  Final bankroll: ${final_bankroll:,.2f}")
        print(f"  Net profit: ${profit:+.2f}")
        print(f"  Win rate: {session_result['bankroll_summary']['win_rate']:.1%}")
        
    except Exception as e:
        print(f"❌ Error during session: {e}")


def show_bankroll_status(agent: BlackjackAgent):
    """Show detailed bankroll status"""
    state = agent.bankroll_manager.get_bankroll_state()
    risk_metrics = agent.bankroll_manager.get_risk_metrics()
    
    print(f"\n💰 Bankroll Status:")
    print(f"  Current: ${state.current_bankroll:,.2f}")
    print(f"  Initial: ${state.initial_bankroll:,.2f}")
    print(f"  Peak: ${state.peak_bankroll:,.2f}")
    print(f"  Net P&L: ${state.net_profit:+,.2f}")
    print(f"  ROI: {state.roi:.1%}")
    print(f"  Hands: {state.total_hands}")
    print(f"  Win Rate: {state.win_rate:.1%}")
    print(f"  Current Drawdown: {state.current_drawdown:.1%}")
    print(f"  Max Drawdown: {state.max_drawdown:.1%}")
    
    if isinstance(risk_metrics, dict):
        print(f"\n📊 Risk Metrics:")
        print(f"  Volatility: {risk_metrics.get('volatility', 0):.3f}")
        print(f"  Sharpe Ratio: {risk_metrics.get('sharpe_ratio', 0):.2f}")
        print(f"  Max Drawdown: {risk_metrics.get('max_drawdown_pct', 0):.1f}%")


def show_recent_hands(agent: BlackjackAgent):
    """Show recent hands"""
    if not agent.game_log:
        print("No hands played yet.")
        return
    
    recent = agent.game_log[-10:]  # Last 10 hands
    
    print(f"\n📊 Recent Hands:")
    print(f"{'Round':<6} {'Bet':<8} {'Player':<15} {'Dealer':<8} {'TC':<6} {'Result':<8}")
    print("-" * 55)
    
    for hand in recent:
        round_num = hand['round']
        bet = f"${hand['initial_bet']:.0f}"
        player = ', '.join(hand['player_cards'][:2])  # First 2 cards
        dealer = hand['dealer_upcard']
        tc = f"{hand['true_count']:.1f}"
        result = f"${hand['net_result']:+.0f}"
        
        print(f"{round_num:<6} {bet:<8} {player:<15} {dealer:<8} {tc:<6} {result:<8}")


def show_session_summary(agent: BlackjackAgent):
    """Show final session summary"""
    state = agent.bankroll_manager.get_bankroll_state()
    
    print(f"\n🎯 Session Summary:")
    print("=" * 30)
    print(f"Hands Played: {state.total_hands}")
    print(f"Initial Bankroll: ${state.initial_bankroll:,.2f}")
    print(f"Final Bankroll: ${state.current_bankroll:,.2f}")
    print(f"Net Profit: ${state.net_profit:+,.2f}")
    print(f"ROI: {state.roi:.1%}")
    print(f"Win Rate: {state.win_rate:.1%}")
    print(f"Max Drawdown: {state.max_drawdown:.1%}")
    
    if state.net_profit > 0:
        print("🎉 Profitable session!")
    elif state.net_profit < 0:
        print("📉 Loss this session")
    else:
        print("🤝 Break-even session")


def run_training():
    """Run self-play training with advanced management"""
    print("\n🏋️ Starting AI Agent Training")
    print("=" * 45)
    
    # 检查训练配置
    training_config_path = "config/training_config.yaml"
    if not os.path.exists(training_config_path):
        print(f"⚠️ 训练配置文件不存在: {training_config_path}")
        print("使用默认配置进行训练")
    
    try:
        # 导入训练管理器
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from train_manager import TrainingManager
        
        # 创建训练管理器
        manager = TrainingManager(training_config_path)
        
        # 显示训练配置
        config = manager.config
        episodes = config["training"]["episodes"]
        rounds = config["training"]["optimization_rounds"]
        processes = config["training"]["parallel_processes"]
        
        print(f"📊 训练配置:")
        print(f"   总手数: {episodes:,}")
        print(f"   优化轮数: {rounds}")
        print(f"   并行进程: {processes}")
        print(f"   学习率: {config['training']['learning_rate']}")
        print(f"   探索率: {config['training']['epsilon_greedy']}")
        
        # 确认开始训练
        print(f"\n预计训练时间: {estimate_training_time(episodes, processes)}")
        confirm = input("是否开始训练? (y/N): ").lower().strip()
        if confirm != 'y':
            print("训练已取消")
            return
        
        # 开始训练
        results = manager.start_training()
        
        # 显示结果
        print(f"\n✅ 训练完成!")
        print(f"📋 训练报告:")
        print(f"   训练ID: {results['training_id']}")
        print(f"   训练时长: {results['training_duration']}")
        print(f"   性能提升: {results['results']['total_improvement']:.6f}")
        print(f"   测试场景: {results['results']['scenarios_tested']}")
        print(f"   模型保存: {results['model_path']}")
        
        # 显示使用方法
        print(f"\n🚀 使用训练好的模型:")
        print(f"   python3 src/main.py --mode play --model-id {results['training_id']}")
        
    except ImportError as e:
        print(f"❌ 无法导入训练管理器: {e}")
        print("请先修复依赖问题:")
        print("   ./fix_numpy.sh")
        print("   或使用: python3 simple_train.py")
    except Exception as e:
        print(f"❌ 训练失败: {e}")
        import traceback
        traceback.print_exc()


def estimate_training_time(episodes: int, processes: int) -> str:
    """估算训练时间"""
    # 基于经验的估算：每1000手约需1-2分钟 (取决于硬件)
    hands_per_minute = 500 * processes  # 并行处理提升
    total_minutes = episodes / hands_per_minute
    
    if total_minutes < 60:
        return f"约 {total_minutes:.0f} 分钟"
    elif total_minutes < 1440:  # 24小时
        hours = total_minutes / 60
        return f"约 {hours:.1f} 小时"
    else:
        days = total_minutes / 1440
        return f"约 {days:.1f} 天"


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Blackjack AI Agent")
    parser.add_argument("--mode", choices=["play", "train", "dashboard", "list-models"], 
                       default="play", help="Run mode")
    parser.add_argument("--config", default="config/config.yaml",
                       help="Config file path")
    parser.add_argument("--hands", type=int, default=100,
                       help="Number of hands for batch play")
    parser.add_argument("--model-id", help="Load specific trained model")
    parser.add_argument("--training-config", default="config/training_config.yaml",
                       help="Training configuration file")
    
    args = parser.parse_args()
    
    # Setup
    print("🃏 Blackjack AI Agent")
    print("=" * 30)
    
    # Create directories
    setup_directories()
    
    # Check Ollama for non-training modes
    if args.mode != "train":
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                print(f"✓ Ollama connected ({len(models)} models available)")
            else:
                print("⚠️  Ollama not responding properly")
        except:
            print("❌ Ollama not available - make sure it's running")
            print("   Install: https://ollama.ai/")
            print("   Start: ollama serve")
            if args.mode == "play":
                return
    
    # Run selected mode
    if args.mode == "play":
        if args.model_id:
            play_with_trained_model(args.model_id)
        else:
            play_interactive_session()
    elif args.mode == "train":
        run_training()
    elif args.mode == "dashboard":
        print("\n🖥️  Starting Streamlit Dashboard...")
        print("Navigate to the URL shown below:")
        run_dashboard()
    elif args.mode == "list-models":
        list_trained_models()
    else:
        parser.print_help()


def play_with_trained_model(model_id: str):
    """使用训练好的模型进行游戏"""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from train_manager import TrainingManager
        
        manager = TrainingManager()
        model_data = manager.load_trained_model(model_id)
        
        print(f"\n🤖 加载训练模型: {model_id}")
        print(f"训练时间: {model_data.get('created_at')}")
        print(f"性能提升: {model_data.get('training_results', {}).get('total_improvement', 0):.6f}")
        
        # TODO: 集成训练结果到 BlackjackAgent
        # 目前先使用标准模式
        play_interactive_session()
        
    except Exception as e:
        print(f"❌ 加载训练模型失败: {e}")
        print("使用标准模式...")
        play_interactive_session()


def list_trained_models():
    """列出所有训练好的模型"""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from train_manager import TrainingManager
        
        manager = TrainingManager()
        models = manager.list_trained_models()
        
        if models:
            print("\n🤖 已训练的模型:")
            print("=" * 50)
            for model in models:
                print(f"📋 模型ID: {model['training_id']}")
                print(f"   创建时间: {model['created_at']}")
                print(f"   性能提升: {model['total_improvement']:.6f}")
                print(f"   文件路径: {model['path']}")
                print()
                
            print("🚀 使用训练模型:")
            print("   python3 src/main.py --mode play --model-id <MODEL_ID>")
        else:
            print("❌ 没有找到已训练的模型")
            print("💡 开始训练: python3 src/main.py --mode train")
            
    except Exception as e:
        print(f"❌ 无法列出模型: {e}")


if __name__ == "__main__":
    main()
