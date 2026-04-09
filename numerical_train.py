#!/usr/bin/env python3
"""
数值训练脚本 - 不使用 LLM
专门用于快速训练决策阈值，使用数值优化方法
"""
import sys
import os
import json
import random
import time
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 预先导入 Action 类
try:
    from src.game.blackjack_env import Action
except ImportError:
    Action = None  # 如果导入失败，稍后再试

def numerical_blackjack_training(episodes=10000, optimization_rounds=10):
    """
    数值训练 - 不使用 LLM，直接优化决策阈值
    """
    print("🔢 数值训练模式 (无 LLM 调用)")
    print("=" * 40)
    
    try:
        # 导入必要的模块
        from src.game.cards import Card, Rank, Suit, Hand, Shoe
        from src.game.blackjack_env import BlackjackEnvironment, Action
        from src.tools.basic_strategy import BasicStrategy
        
        print("✅ 核心模块导入成功")
        
        # 初始化组件
        env = BlackjackEnvironment()
        basic_strategy = BasicStrategy()
        
        # 训练参数
        current_thresholds = {
            "hit_stand": 0.0,      # Hit/Stand 阈值
            "double_down": 0.5,    # Double Down 阈值
            "split": 0.3,          # Split 阈值
            "surrender": -0.8,     # Surrender 阈值
        }
        
        best_performance = float('-inf')
        best_thresholds = current_thresholds.copy()
        improvements = []
        
        print(f"📊 训练参数:")
        print(f"   总手数: {episodes:,}")
        print(f"   优化轮数: {optimization_rounds}")
        print(f"   预计时间: 2-5 分钟")
        
        # 开始优化训练
        for round_num in range(optimization_rounds):
            print(f"\n🔄 优化轮次 {round_num + 1}/{optimization_rounds}")
            
            # 测试当前阈值
            performance = evaluate_strategy_numerical(
                env, basic_strategy, current_thresholds, episodes // optimization_rounds
            )
            
            print(f"   当前性能: {performance:.6f}")
            
            # 记录改进
            if performance > best_performance:
                improvement = performance - best_performance
                improvements.append(improvement)
                best_performance = performance
                best_thresholds = current_thresholds.copy()
                print(f"   🎉 新的最佳性能! 改进: {improvement:.6f}")
            else:
                improvements.append(0.0)
                print(f"   📊 无改进")
            
            # 调整阈值 (简单的随机搜索)
            current_thresholds = adjust_thresholds(current_thresholds, best_performance)
            
            # 显示进度
            progress = (round_num + 1) / optimization_rounds * 100
            print(f"   进度: {progress:.1f}%")
        
        total_improvement = sum(improvements)
        
        # 保存结果
        results = save_numerical_results(
            best_thresholds, best_performance, total_improvement, improvements
        )
        
        print(f"\n🎉 数值训练完成!")
        print(f"📊 最终结果:")
        print(f"   最佳性能: {best_performance:.6f}")
        print(f"   总改进: {total_improvement:.6f}")
        print(f"   平均改进: {total_improvement/optimization_rounds:.6f}")
        print(f"   模型已保存: {results['model_path']}")
        
        return results
        
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return None
    except Exception as e:
        print(f"❌ 训练失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def evaluate_strategy_numerical(env, basic_strategy, thresholds, episodes):
    """
    数值评估策略性能 - 不使用 LLM
    """
    total_profit = 0
    games_played = 0
    
    for episode in range(episodes):
        try:
            # 重置环境
            env.reset()
            
            # 模拟一手游戏
            profit = simulate_hand_numerical(env, basic_strategy, thresholds)
            total_profit += profit
            games_played += 1
            
            # 显示进度 (每1000手)
            if (episode + 1) % 1000 == 0:
                current_avg = total_profit / games_played if games_played > 0 else 0
                print(f"      已完成: {episode + 1:,}/{episodes:,}, 当前平均: {current_avg:.6f}")
        
        except Exception as e:
            # 跳过有问题的手牌
            continue
    
    return total_profit / games_played if games_played > 0 else 0


def simulate_hand_numerical(env, basic_strategy, thresholds):
    """
    数值模拟一手牌 - 使用基本策略 + 阈值调整
    """
    try:
        # 发初始牌
        env.deal_initial_cards()
        
        # 获取玩家手牌和庄家明牌
        player_hand = env.game_state.player_hands[0]
        dealer_upcard = env.game_state.dealer_hand.cards[0]
        
        # 玩家决策阶段
        while not env.game_state.player_hands[0].is_finished:
            # 获取可用动作
            available_actions = env._get_available_actions(0)
            
            # 使用基本策略 + 阈值调整
            action, _, _ = basic_strategy.get_recommendation(
                player_hand, dealer_upcard, available_actions
            )
            
            # 应用阈值调整 (简化版)
            action = apply_threshold_adjustment(action, thresholds, player_hand, dealer_upcard)
            
            # 执行动作
            env.step(action)
        
        # 庄家打牌
        env._dealer_play()
        
        # 计算结果
        result = env._determine_winner()
        profit = result.get('profit', 0)
        
        return profit
        
    except Exception as e:
        # 返回 0 利润如果出现错误
        return 0


def apply_threshold_adjustment(action, thresholds, player_hand, dealer_upcard):
    """
    基于阈值调整动作
    """
    # 导入 Action (避免全局导入问题)
    from src.game.blackjack_env import Action
    
    # 简化的阈值逻辑
    hand_value = player_hand.value
    dealer_value = dealer_upcard.blackjack_value
    
    # 基本的阈值调整 (这里可以实现更复杂的逻辑)
    if action == Action.HIT and hand_value >= 17:
        # 根据 hit_stand 阈值决定是否改为 Stand
        if random.random() < (0.5 + thresholds["hit_stand"]):
            action = Action.STAND
    
    return action


def adjust_thresholds(current_thresholds, performance):
    """
    调整阈值 - 简单的随机搜索
    """
    new_thresholds = current_thresholds.copy()
    
    # 随机调整一个阈值
    threshold_name = random.choice(list(new_thresholds.keys()))
    adjustment = random.uniform(-0.1, 0.1)
    new_thresholds[threshold_name] += adjustment
    
    # 保持阈值在合理范围内
    new_thresholds[threshold_name] = max(-2.0, min(2.0, new_thresholds[threshold_name]))
    
    return new_thresholds


def save_numerical_results(thresholds, performance, total_improvement, improvements):
    """
    保存数值训练结果
    """
    try:
        # 创建结果目录
        results_dir = Path("models/numerical_training")
        results_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存模型文件
        model_file = results_dir / f"numerical_model_{timestamp}.json"
        
        model_data = {
            "training_type": "numerical_optimization",
            "timestamp": datetime.now().isoformat(),
            "thresholds": thresholds,
            "performance": performance,
            "total_improvement": total_improvement,
            "improvements": improvements,
            "status": "completed"
        }
        
        with open(model_file, 'w', encoding='utf-8') as f:
            json.dump(model_data, f, indent=2, ensure_ascii=False)
        
        print(f"📁 模型已保存: {model_file}")
        
        return {
            "model_path": str(model_file),
            "performance": performance,
            "thresholds": thresholds
        }
        
    except Exception as e:
        print(f"⚠️ 保存结果失败: {e}")
        return {"model_path": "未保存", "performance": performance, "thresholds": thresholds}


def quick_numerical_demo():
    """
    快速数值训练演示
    """
    print("🚀 快速数值训练演示")
    return numerical_blackjack_training(episodes=2000, optimization_rounds=5)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Blackjack AI 数值训练 (无 LLM)")
    parser.add_argument("--episodes", type=int, default=10000, 
                       help="训练手数 (默认: 10,000)")
    parser.add_argument("--rounds", type=int, default=10,
                       help="优化轮数 (默认: 10)")
    parser.add_argument("--demo", action="store_true",
                       help="快速演示模式")
    
    args = parser.parse_args()
    
    if args.demo:
        quick_numerical_demo()
    else:
        numerical_blackjack_training(args.episodes, args.rounds)
