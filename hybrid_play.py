#!/usr/bin/env python3
"""
混合模型游戏脚本 - 使用训练好的混合模型进行游戏
支持加载不同阶段的模型：数值模型、LLM增强模型、混合模型
"""
import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

class HybridModelPlayer:
    """混合模型玩家"""
    
    def __init__(self):
        self.available_models = []
        self.current_model = None
        self.model_data = None
        
    def scan_available_models(self):
        """扫描可用的模型"""
        models = []
        
        # 扫描混合训练模型
        hybrid_dir = Path("models/hybrid_training")
        if hybrid_dir.exists():
            for model_file in hybrid_dir.glob("hybrid_model_*.json"):
                try:
                    with open(model_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    models.append({
                        "id": model_file.stem,
                        "type": "hybrid",
                        "path": str(model_file),
                        "timestamp": data.get("timestamp", "未知"),
                        "performance": data.get("performance_summary", {}),
                        "description": "混合训练模型 (数值+LLM)"
                    })
                except Exception as e:
                    continue
        
        # 扫描数值训练模型
        numerical_dir = Path("models/numerical_training")
        if numerical_dir.exists():
            for model_file in numerical_dir.glob("numerical_model_*.json"):
                try:
                    with open(model_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    models.append({
                        "id": model_file.stem,
                        "type": "numerical",
                        "path": str(model_file),
                        "timestamp": data.get("timestamp", "未知"),
                        "performance": data.get("performance", 0),
                        "description": "纯数值训练模型"
                    })
                except Exception as e:
                    continue
        
        # 按时间排序，最新的在前面
        models.sort(key=lambda x: x["timestamp"], reverse=True)
        
        self.available_models = models
        return models
    
    def list_models(self):
        """列出可用模型"""
        models = self.scan_available_models()
        
        print("🎯 可用的训练模型:")
        print("=" * 50)
        
        if not models:
            print("❌ 未找到训练好的模型")
            print("💡 请先运行训练:")
            print("   python3 hybrid_train.py --mode demo")
            return
        
        for i, model in enumerate(models, 1):
            print(f"\n{i}. {model['id']}")
            print(f"   类型: {model['description']}")
            print(f"   时间: {model['timestamp'][:19].replace('T', ' ')}")
            
            if model['type'] == 'hybrid':
                perf = model['performance']
                print(f"   胜率: {perf.get('game_win_rate', 0):.1%}")
                print(f"   平均利润: {perf.get('game_avg_profit', 0):.4f}")
            elif model['type'] == 'numerical':
                print(f"   性能: {model['performance']}")
        
        print(f"\n📊 共找到 {len(models)} 个模型")
    
    def load_model(self, model_id: str = None):
        """加载指定模型"""
        models = self.scan_available_models()
        
        if not models:
            print("❌ 没有可用的模型")
            return False
        
        # 如果没有指定模型，使用最新的
        if model_id is None:
            selected_model = models[0]
            print(f"🔄 自动选择最新模型: {selected_model['id']}")
        else:
            # 查找指定模型
            selected_model = None
            for model in models:
                if model['id'] == model_id or model['path'].endswith(f"{model_id}.json"):
                    selected_model = model
                    break
            
            if not selected_model:
                print(f"❌ 未找到模型: {model_id}")
                return False
        
        try:
            # 加载模型数据
            with open(selected_model['path'], 'r', encoding='utf-8') as f:
                self.model_data = json.load(f)
            
            self.current_model = selected_model
            
            print(f"✅ 成功加载模型: {selected_model['description']}")
            print(f"   模型ID: {selected_model['id']}")
            
            if selected_model['type'] == 'hybrid':
                self._print_hybrid_model_info()
            
            return True
            
        except Exception as e:
            print(f"❌ 加载模型失败: {e}")
            return False
    
    def _print_hybrid_model_info(self):
        """打印混合模型信息"""
        if not self.model_data:
            return
        
        components = self.model_data.get("components", {})
        performance = self.model_data.get("performance_summary", {})
        
        print(f"\n📋 混合模型详情:")
        print(f"   数值基础参数:")
        base_thresholds = components.get("numerical_base", {})
        for key, value in base_thresholds.items():
            print(f"      {key}: {value}")
        
        print(f"   LLM改进程度: {components.get('llm_adjustments', 0):.4f}")
        print(f"   游戏性能: {components.get('game_performance', 0):.4f}")
        print(f"   胜率: {performance.get('game_win_rate', 0):.1%}")
    
    def play_interactive_game(self, rounds: int = 10):
        """进行交互式游戏"""
        if not self.current_model:
            print("❌ 请先加载模型")
            return
        
        print(f"\n🎮 开始互动游戏 ({rounds} 轮)")
        print(f"使用模型: {self.current_model['description']}")
        print("=" * 40)
        
        try:
            # 导入游戏模块
            from src.game.cards import Card, Rank, Suit, Hand, Shoe
            from src.game.blackjack_env import BlackjackEnvironment, Action
            from src.tools.basic_strategy import BasicStrategy
            
            env = BlackjackEnvironment()
            basic_strategy = BasicStrategy()
            
            total_profit = 0
            wins = 0
            
            for round_num in range(1, rounds + 1):
                print(f"\n🎲 第 {round_num} 轮游戏")
                print("-" * 20)
                
                # 开始新游戏 (自动发牌)
                env.start_new_round()
                
                # 显示牌面
                player_hand = env.game_state.player_hands[0]
                dealer_upcard = env.game_state.dealer_hand.cards[0]
                
                print(f"玩家手牌: {self._format_hand(player_hand)} (点数: {player_hand.value})")
                print(f"庄家明牌: {dealer_upcard}")
                
                # 玩家决策
                game_over = False
                while not game_over:
                    # 检查是否已经结束 (21点或爆牌)
                    if player_hand.value >= 21:
                        if player_hand.value == 21:
                            print(f"🎉 21点!")
                        else:
                            print(f"💥 爆牌! ({player_hand.value})")
                        game_over = True
                        break
                    
                    available_actions = env.get_valid_actions(0)
                    
                    if not available_actions:
                        game_over = True
                        break
                    
                    # 使用模型决策
                    action = self._make_model_decision(player_hand, dealer_upcard, available_actions)
                    
                    print(f"模型决策: {action.name}")
                    
                    # 执行动作
                    if action == Action.STAND:
                        print(f"停牌")
                        game_over = True
                    else:
                        env.take_action(action, 0)
                        
                        # 显示新手牌
                        if action == Action.HIT:
                            print(f"新手牌: {self._format_hand(player_hand)} (点数: {player_hand.value})")
                
                # 庄家打牌
                print(f"庄家打牌...")
                
                # 设置游戏结束状态以触发庄家打牌
                env.game_state.current_hand_index = len(env.game_state.player_hands)
                
                env.play_dealer()
                dealer_hand = env.game_state.dealer_hand
                print(f"庄家手牌: {self._format_hand(dealer_hand)} (点数: {dealer_hand.value})")
                
                # 结算
                results = env.calculate_results()
                game_result, payout = results[0]  # 获取第一手牌结果
                
                # 计算净利润 (payout - bet)
                bet = env.game_state.player_hands[0].bet
                net_profit = payout - bet
                total_profit += net_profit
                
                if net_profit > 0:
                    wins += 1
                    print(f"🎉 获胜! 利润: +{net_profit}")
                elif net_profit == 0:
                    print(f"🤝 平局! 利润: {net_profit}")
                else:
                    print(f"😞 输了! 利润: {net_profit}")
                
                print(f"当前总利润: {total_profit:.2f}")
            
            # 最终统计
            win_rate = wins / rounds
            avg_profit = total_profit / rounds
            
            print(f"\n📊 游戏总结:")
            print(f"   总轮数: {rounds}")
            print(f"   获胜: {wins} 轮")
            print(f"   胜率: {win_rate:.1%}")
            print(f"   总利润: {total_profit:.2f}")
            print(f"   平均利润: {avg_profit:.4f}")
            
        except Exception as e:
            print(f"❌ 游戏出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _make_model_decision(self, player_hand, dealer_upcard, available_actions):
        """基于模型做决策"""
        if not self.model_data:
            # 回退到基本策略
            from src.tools.basic_strategy import BasicStrategy
            strategy = BasicStrategy()
            action, _, _ = strategy.get_recommendation(player_hand, dealer_upcard, available_actions)
            return action
        
        if self.current_model['type'] == 'hybrid':
            # 使用混合模型决策
            return self._hybrid_model_decision(player_hand, dealer_upcard, available_actions)
        elif self.current_model['type'] == 'numerical':
            # 使用数值模型决策
            return self._numerical_model_decision(player_hand, dealer_upcard, available_actions)
        else:
            # 默认基本策略
            from src.tools.basic_strategy import BasicStrategy
            strategy = BasicStrategy()
            action, _, _ = strategy.get_recommendation(player_hand, dealer_upcard, available_actions)
            return action
    
    def _hybrid_model_decision(self, player_hand, dealer_upcard, available_actions):
        """混合模型决策"""
        # 导入 Action
        from src.game.blackjack_env import Action
        
        # 获取基本策略推荐
        from src.tools.basic_strategy import BasicStrategy
        strategy = BasicStrategy()
        base_action, _, confidence = strategy.get_recommendation(player_hand, dealer_upcard, available_actions)
        
        # 应用混合模型的调整
        components = self.model_data.get("components", {})
        numerical_base = components.get("numerical_base", {})
        llm_adjustment = components.get("llm_adjustments", 0)
        
        # 简化的混合决策逻辑
        hand_value = player_hand.value
        dealer_value = dealer_upcard.value
        
        # 应用数值调整
        if base_action == Action.HIT and hand_value >= 17:
            hit_threshold = numerical_base.get("hit_stand", 0)
            if hit_threshold > 0.2:  # 阈值较高时更倾向于 stand
                base_action = Action.STAND
        
        return base_action
    
    def _numerical_model_decision(self, player_hand, dealer_upcard, available_actions):
        """数值模型决策"""
        # 导入 Action
        from src.game.blackjack_env import Action
        
        # 获取基本策略推荐
        from src.tools.basic_strategy import BasicStrategy
        strategy = BasicStrategy()
        base_action, _, confidence = strategy.get_recommendation(player_hand, dealer_upcard, available_actions)
        
        # 应用数值模型的阈值调整
        thresholds = self.model_data.get("thresholds", {})
        
        hand_value = player_hand.value
        
        # 简化的阈值应用
        if base_action == Action.HIT and hand_value >= 17:
            hit_threshold = thresholds.get("hit_stand", 0)
            if hit_threshold > 0.2:
                base_action = Action.STAND
        
        return base_action
    
    def _format_hand(self, hand):
        """格式化手牌显示"""
        return " ".join([str(card) for card in hand.cards])
    
    def benchmark_model(self, episodes: int = 1000):
        """基准测试模型性能"""
        if not self.current_model:
            print("❌ 请先加载模型")
            return
        
        print(f"\n🧪 基准测试 ({episodes:,} 手)")
        print(f"使用模型: {self.current_model['description']}")
        print("=" * 40)
        
        try:
            # 导入模块
            from src.game.cards import Card, Rank, Suit, Hand, Shoe
            from src.game.blackjack_env import BlackjackEnvironment, Action
            from src.tools.basic_strategy import BasicStrategy
            
            # 预先创建对象以提高性能
            env = BlackjackEnvironment()
            self.basic_strategy = BasicStrategy()  # 缓存基本策略对象
            print("✅ 初始化完成，开始基准测试...")
            
            total_profit = 0
            wins = 0
            pushes = 0
            losses = 0
            errors = 0
            
            for episode in range(episodes):
                try:
                    # 开始新一轮 (自动发牌)
                    env.start_new_round()
                    
                    player_hand = env.game_state.player_hands[0]
                    dealer_upcard = env.game_state.dealer_hand.cards[0]
                    
                    # 玩家决策 - 简化版本
                    game_over = False
                    max_actions = 10  # 防止无限循环
                    action_count = 0
                    
                    while not game_over and action_count < max_actions:
                        # 检查是否已经结束 (21点或爆牌)
                        if player_hand.value >= 21:
                            game_over = True
                            break
                        
                        available_actions = env.get_valid_actions(0)
                        
                        if not available_actions:
                            game_over = True
                            break
                        
                        action = self._make_model_decision_fast(player_hand, dealer_upcard, available_actions)
                        
                        # 执行动作
                        if action == Action.STAND:
                            game_over = True
                        else:
                            env.take_action(action, 0)
                        
                        action_count += 1
                    
                    # 庄家打牌
                    env.game_state.current_hand_index = len(env.game_state.player_hands)
                    env.play_dealer()
                    
                    # 结算
                    results = env.calculate_results()
                    if results and len(results) > 0:
                        game_result, payout = results[0]  # 获取第一手牌结果
                        
                        # 计算净利润 (payout - bet)
                        bet = env.game_state.player_hands[0].bet
                        net_profit = payout - bet
                        total_profit += net_profit
                        
                        if net_profit > 0:
                            wins += 1
                        elif net_profit == 0:
                            pushes += 1
                        else:
                            losses += 1
                    else:
                        # 结算失败，记录错误
                        errors += 1
                
                except Exception as e:
                    # 跳过有问题的手牌，但记录错误
                    errors += 1
                    if errors <= 5:  # 只显示前5个错误
                        print(f"   错误 {errors}: {str(e)[:50]}")
                    continue
                
                # 显示进度
                if (episode + 1) % 50 == 0:
                    current_avg = total_profit / max(1, episode + 1 - errors)
                    print(f"   进度: {episode + 1:,}/{episodes:,}, 当前平均: {current_avg:.4f}, 错误: {errors}")
            
            # 最终统计
            valid_episodes = episodes - errors
            if valid_episodes > 0:
                win_rate = wins / valid_episodes
                push_rate = pushes / valid_episodes  
                loss_rate = losses / valid_episodes
                avg_profit = total_profit / valid_episodes
            else:
                win_rate = push_rate = loss_rate = avg_profit = 0
            
            print(f"\n📊 基准测试结果:")
            print(f"   总手数: {episodes:,}")
            print(f"   有效手数: {valid_episodes:,}")
            print(f"   错误手数: {errors:,}")
            print(f"   获胜: {wins:,} ({win_rate:.1%})")
            print(f"   平局: {pushes:,} ({push_rate:.1%})")
            print(f"   失败: {losses:,} ({loss_rate:.1%})")
            print(f"   总利润: {total_profit:.2f}")
            print(f"   平均利润: {avg_profit:.6f}")
            if valid_episodes > 0:
                print(f"   预期小时利润: {avg_profit * 100:.2f} (假设每小时100手)")
            
        except Exception as e:
            print(f"❌ 基准测试出错: {e}")
    
    def _make_model_decision_fast(self, player_hand, dealer_upcard, available_actions):
        """快速模型决策 - 用于基准测试"""
        # 导入 Action
        from src.game.blackjack_env import Action
        
        # 使用缓存的基本策略对象
        if hasattr(self, 'basic_strategy'):
            strategy = self.basic_strategy
        else:
            from src.tools.basic_strategy import BasicStrategy
            self.basic_strategy = BasicStrategy()
            strategy = self.basic_strategy
        
        # 获取基本策略推荐
        base_action, _, confidence = strategy.get_recommendation(player_hand, dealer_upcard, available_actions)
        
        # 简化的模型调整
        if self.current_model['type'] == 'hybrid':
            components = self.model_data.get("components", {})
            numerical_base = components.get("numerical_base", {})
            
            hand_value = player_hand.value
            
            # 简化的混合决策逻辑
            if base_action == Action.HIT and hand_value >= 17:
                hit_threshold = numerical_base.get("hit_stand", 0)
                if hit_threshold > 0.2:
                    base_action = Action.STAND
        
        return base_action


def main():
    """主函数"""
    player = HybridModelPlayer()
    
    import argparse
    parser = argparse.ArgumentParser(description="混合模型游戏系统")
    parser.add_argument("--mode", choices=["list", "play", "benchmark"], 
                       default="list", help="运行模式")
    parser.add_argument("--model", type=str, default=None,
                       help="指定模型ID")
    parser.add_argument("--rounds", type=int, default=10,
                       help="游戏轮数")
    parser.add_argument("--episodes", type=int, default=1000,
                       help="基准测试手数")
    
    args = parser.parse_args()
    
    if args.mode == "list":
        player.list_models()
    elif args.mode == "play":
        if player.load_model(args.model):
            player.play_interactive_game(args.rounds)
    elif args.mode == "benchmark":
        if player.load_model(args.model):
            player.benchmark_model(args.episodes)


if __name__ == "__main__":
    main()
