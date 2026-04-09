#!/usr/bin/env python3
"""
21点游戏模拟器 - 轻量级终端版本
包含AI助手、自主决策、性能报告等功能
"""
import os
import sys
import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from src.game.cards import Card, Deck, Shoe
    from src.game.blackjack_env import BlackjackEnvironment
    # from src.tools.basic_strategy import BasicStrategy
except ImportError as e:
    print(f"⚠️  导入模块失败: {e}")
    print("尝试创建简化版游戏环境...")
    
    # 简化的Card和Shoe实现
    class Card:
        def __init__(self, rank, suit):
            self.rank = rank
            self.suit = suit
        
        def __str__(self):
            return f"{self.rank} of {self.suit}"
    
    class Shoe:
        def __init__(self, num_decks=1, penetration=0.75):
            self.cards = []
            self.num_decks = num_decks
            self.penetration = penetration
            self.reset_shoe()
        
        def reset_shoe(self):
            suits = ["Hearts", "Diamonds", "Clubs", "Spades"]
            ranks = ["Ace", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King"]
            
            self.cards = []
            for _ in range(self.num_decks):
                for suit in suits:
                    for rank in ranks:
                        self.cards.append(Card(rank, suit))
            
            random.shuffle(self.cards)
        
        def deal_card(self):
            if len(self.cards) < 10:  # 重新洗牌
                self.reset_shoe()
            return self.cards.pop()
    
    class BlackjackEnvironment:
        def __init__(self):
            self.shoe = None
    
    print("✅ 使用简化版游戏环境")

class TerminalBlackjackSimulator:
    """终端版21点游戏模拟器"""
    
    def __init__(self):
        self.player_chips = 300
        self.current_bet = 10
        self.game_history = []
        self.current_hand = None
        self.ai_decision = None
        self.num_decks = 1
        self.game_env = None
        self.selected_model = None
        
    def run(self):
        """运行主界面"""
        self.show_welcome()
        
        if not self.setup_game():
            return
            
        while self.player_chips > 0:
            self.show_status()
            
            if not self.current_hand:
                if not self.start_new_hand():
                    break
            elif self.current_hand.get('game_over', False):
                self.show_hand_result()
                self.current_hand = None
                input("\n按回车继续下一局...")
            else:
                if not self.player_action():
                    break
        
        self.show_final_report()
    
    def show_welcome(self):
        """显示欢迎界面"""
        print("\n" + "="*60)
        print("🃏" + " "*20 + "21点游戏模拟器" + " "*20 + "🃏")
        print("="*60)
        print("欢迎来到专业的21点游戏体验！")
        print("💰 初始筹码: $300")
        print("🎯 目标: 通过智慧和策略获得更多筹码")
        print("🤖 AI助手: 随时提供专业建议")
        print("="*60)
    
    def setup_game(self):
        """设置游戏参数"""
        print("\n🎮 游戏设置")
        print("-" * 30)
        
        # 选择牌副数
        while True:
            try:
                decks = input("选择牌副数 (1-8, 默认1): ").strip()
                if not decks:
                    decks = 1
                else:
                    decks = int(decks)
                
                if 1 <= decks <= 8:
                    self.num_decks = decks
                    break
                else:
                    print("❌ 请输入1-8之间的数字")
            except ValueError:
                print("❌ 请输入有效数字")
        
        # 扫描可用模型
        available_models = self.scan_available_models()
        if available_models:
            print(f"\n🤖 发现 {len(available_models)} 个可用AI模型:")
            for i, model in enumerate(available_models, 1):
                print(f"  {i}. {model['id']} ({model['type']})")
            
            while True:
                try:
                    choice = input(f"\n选择AI模型 (1-{len(available_models)}, 回车跳过): ").strip()
                    if not choice:
                        self.selected_model = None
                        break
                    
                    idx = int(choice) - 1
                    if 0 <= idx < len(available_models):
                        self.selected_model = available_models[idx]
                        print(f"✅ 已选择: {self.selected_model['id']}")
                        break
                    else:
                        print(f"❌ 请输入1-{len(available_models)}之间的数字")
                except ValueError:
                    print("❌ 请输入有效数字")
        else:
            print("⚠️  未找到可用的AI模型")
            print("💡 提示: 运行 'python3 hybrid_train.py --mode demo' 来训练一个演示模型")
            self.selected_model = None
        
        # 初始化游戏环境
        try:
            self.game_env = BlackjackEnvironment()
            self.game_env.shoe = Shoe(num_decks=self.num_decks, penetration=0.75)
            print(f"\n✅ 游戏环境初始化成功 ({self.num_decks}副牌)")
            return True
        except Exception as e:
            print(f"❌ 游戏初始化失败: {e}")
            return False
    
    def show_status(self):
        """显示当前状态"""
        print("\n" + "="*60)
        print(f"💰 筹码: ${self.player_chips}  |  🎯 下注: ${self.current_bet}  |  🎲 总局数: {len(self.game_history)}")
        
        if self.game_history:
            wins = sum(1 for game in self.game_history if game['result'] == 'win')
            win_rate = wins / len(self.game_history)
            total_profit = sum(game['profit'] for game in self.game_history)
            print(f"📈 胜率: {win_rate:.1%}  |  💹 总盈亏: ${total_profit:+.0f}")
        
        print("-" * 60)
    
    def start_new_hand(self):
        """开始新局"""
        print("\n🎰 开始新局")
        
        # 设置下注
        max_bet = min(self.player_chips, 100)
        if max_bet <= 0:
            print("💸 筹码不足，游戏结束！")
            return False
        
        while True:
            try:
                bet_input = input(f"下注金额 (1-{max_bet}, 默认{min(10, max_bet)}): ").strip()
                if not bet_input:
                    bet = min(10, max_bet)
                else:
                    bet = int(bet_input)
                
                if 1 <= bet <= max_bet:
                    self.current_bet = bet
                    break
                else:
                    print(f"❌ 请输入1-{max_bet}之间的金额")
            except ValueError:
                print("❌ 请输入有效数字")
        
        # 发牌
        print(f"\n💰 下注: ${self.current_bet}")
        print("🎲 发牌中...")
        time.sleep(1)
        
        self.deal_new_hand()
        self.show_table()
        
        return True
    
    def deal_new_hand(self):
        """发新牌"""
        # 扣除下注
        self.player_chips -= self.current_bet
        
        # 模拟发牌
        player_cards = [
            self.game_env.shoe.deal_card(),
            self.game_env.shoe.deal_card()
        ]
        dealer_cards = [
            self.game_env.shoe.deal_card(),
            self.game_env.shoe.deal_card()
        ]
        
        # 计算点数
        player_total = self.calculate_hand_value(player_cards)
        dealer_upcard_value = self.get_card_value(dealer_cards[0])
        
        # 设置当前手牌状态
        self.current_hand = {
            'player_cards': [str(card) for card in player_cards],
            'dealer_cards': [str(card) for card in dealer_cards],
            'player_total': player_total,
            'dealer_upcard': dealer_upcard_value,
            'game_over': False,
            'can_double': len(player_cards) == 2,
            'can_split': self.check_can_split(player_cards)
        }
        
        # 检查自然21点
        if player_total == 21:
            dealer_total = self.calculate_hand_value(dealer_cards)
            self.finish_hand(dealer_total)
    
    def show_table(self):
        """显示游戏桌面"""
        if not self.current_hand:
            return
        
        print("\n🏛️  庄家:")
        dealer_cards = self.current_hand['dealer_cards']
        
        if self.current_hand.get('game_over', False):
            # 游戏结束，显示所有牌
            cards_display = "  ".join([self.format_card(card) for card in dealer_cards])
            dealer_total = self.current_hand.get('dealer_total', 0)
            print(f"   {cards_display}  (点数: {dealer_total})")
        else:
            # 游戏中，隐藏第二张牌
            visible_card = self.format_card(dealer_cards[0])
            print(f"   {visible_card}  🂠  (点数: ?)")
        
        print("\n👤 玩家:")
        player_cards = self.current_hand['player_cards']
        cards_display = "  ".join([self.format_card(card) for card in player_cards])
        player_total = self.current_hand['player_total']
        print(f"   {cards_display}  (点数: {player_total})")
    
    def format_card(self, card_str):
        """格式化卡牌显示"""
        if 'Hearts' in card_str or 'Diamonds' in card_str:
            suit_symbol = "♥" if 'Hearts' in card_str else "♦"
            color_code = "\033[91m"  # 红色
        else:
            suit_symbol = "♠" if 'Spades' in card_str else "♣"
            color_code = "\033[90m"  # 深灰色
        
        rank = card_str.split(' of ')[0]
        if rank == "Ace":
            rank = "A"
        elif rank == "Jack":
            rank = "J"
        elif rank == "Queen":
            rank = "Q"
        elif rank == "King":
            rank = "K"
        
        return f"{color_code}[{rank}{suit_symbol}]\033[0m"
    
    def player_action(self):
        """玩家行动"""
        print("\n🎯 你的回合")
        
        # 显示可用行动
        actions = ["1. 要牌 (Hit)", "2. 停牌 (Stand)"]
        
        if self.current_hand.get('can_double') and self.player_chips >= self.current_bet:
            actions.append("3. 加倍 (Double)")
        
        if self.current_hand.get('can_split') and self.player_chips >= self.current_bet:
            actions.append("4. 分牌 (Split)")
        
        if self.selected_model:
            actions.append("5. AI建议")
        
        actions.extend(["0. 退出游戏", "R. 查看报告"])
        
        print("可选行动:")
        for action in actions:
            print(f"  {action}")
        
        while True:
            choice = input("\n选择行动: ").strip().upper()
            
            if choice == "1":
                self.player_hit()
                return True
            elif choice == "2":
                self.player_stand()
                return True
            elif choice == "3" and self.current_hand.get('can_double') and self.player_chips >= self.current_bet:
                self.player_double()
                return True
            elif choice == "4" and self.current_hand.get('can_split') and self.player_chips >= self.current_bet:
                print("🚧 分牌功能正在开发中...")
                continue
            elif choice == "5" and self.selected_model:
                self.get_ai_decision()
                continue
            elif choice == "0":
                print("👋 感谢游戏！")
                return False
            elif choice == "R":
                self.show_game_report()
                continue
            else:
                print("❌ 无效选择，请重新输入")
    
    def player_hit(self):
        """玩家要牌"""
        print("\n🟢 要牌...")
        time.sleep(0.5)
        
        # 发一张牌
        new_card = self.game_env.shoe.deal_card()
        self.current_hand['player_cards'].append(str(new_card))
        
        # 重新计算点数
        player_cards = [self.parse_card_string(card) for card in self.current_hand['player_cards']]
        player_total = self.calculate_hand_value(player_cards)
        self.current_hand['player_total'] = player_total
        self.current_hand['can_double'] = False
        
        print(f"抽到: {self.format_card(str(new_card))}")
        self.show_table()
        
        # 检查是否爆牌
        if player_total > 21:
            print("💥 爆牌！")
            self.finish_hand_bust()
    
    def player_stand(self):
        """玩家停牌"""
        print("\n🔴 停牌...")
        time.sleep(0.5)
        
        # 庄家行动
        self.dealer_play()
    
    def player_double(self):
        """玩家加倍"""
        print("\n🟡 加倍...")
        time.sleep(0.5)
        
        # 双倍下注
        self.player_chips -= self.current_bet
        self.current_bet *= 2
        print(f"💰 下注增加到: ${self.current_bet}")
        
        # 只能拿一张牌
        new_card = self.game_env.shoe.deal_card()
        self.current_hand['player_cards'].append(str(new_card))
        
        # 重新计算点数
        player_cards = [self.parse_card_string(card) for card in self.current_hand['player_cards']]
        player_total = self.calculate_hand_value(player_cards)
        self.current_hand['player_total'] = player_total
        
        print(f"抽到: {self.format_card(str(new_card))}")
        self.show_table()
        
        # 如果没有爆牌，庄家行动
        if player_total <= 21:
            self.dealer_play()
        else:
            print("💥 爆牌！")
            self.finish_hand_bust()
    
    def dealer_play(self):
        """庄家行动"""
        print("\n🏛️  庄家行动...")
        time.sleep(1)
        
        dealer_cards = [self.parse_card_string(card) for card in self.current_hand['dealer_cards']]
        
        # 庄家必须在16点或以下要牌，17点或以上停牌
        while True:
            dealer_total = self.calculate_hand_value(dealer_cards)
            print(f"庄家点数: {dealer_total}")
            
            if dealer_total >= 17:
                break
            
            print("庄家要牌...")
            time.sleep(1)
            
            # 庄家要牌
            new_card = self.game_env.shoe.deal_card()
            dealer_cards.append(new_card)
            self.current_hand['dealer_cards'].append(str(new_card))
            print(f"庄家抽到: {self.format_card(str(new_card))}")
        
        dealer_total = self.calculate_hand_value(dealer_cards)
        self.finish_hand(dealer_total)
    
    def finish_hand(self, dealer_total):
        """结束手牌，计算结果"""
        player_total = self.current_hand['player_total']
        
        # 判断胜负
        if player_total > 21:
            outcome = 'loss'
            profit = -self.current_bet
            result_text = "💥 玩家爆牌 - 失败"
        elif dealer_total > 21:
            outcome = 'win'
            profit = self.current_bet
            result_text = "🎉 庄家爆牌 - 获胜"
        elif player_total > dealer_total:
            outcome = 'win'
            profit = self.current_bet
            result_text = f"🎉 点数更高 ({player_total} vs {dealer_total}) - 获胜"
        elif player_total < dealer_total:
            outcome = 'loss'
            profit = -self.current_bet
            result_text = f"😞 点数不够 ({player_total} vs {dealer_total}) - 失败"
        else:
            outcome = 'push'
            profit = 0
            result_text = f"🤝 平局 ({player_total} vs {dealer_total})"
        
        # 检查自然21点奖励
        if (player_total == 21 and len(self.current_hand['player_cards']) == 2 
            and outcome == 'win'):
            profit = int(self.current_bet * 1.5)  # 3:2赔率
            result_text = "🌟 黑杰克！(21点) - 获胜"
        
        # 更新筹码
        self.player_chips += self.current_bet + profit
        
        # 记录结果
        self.current_hand.update({
            'game_over': True,
            'dealer_total': dealer_total,
            'result_text': result_text,
            'result': {
                'outcome': outcome,
                'profit': profit,
                'player_total': player_total,
                'dealer_total': dealer_total
            }
        })
        
        # 添加到历史记录
        self.game_history.append({
            'timestamp': datetime.now(),
            'bet': self.current_bet,
            'player_total': player_total,
            'dealer_total': dealer_total,
            'result': outcome,
            'profit': profit,
            'player_cards': self.current_hand['player_cards'][:],
            'dealer_cards': self.current_hand['dealer_cards'][:]
        })
        
        self.show_table()
    
    def finish_hand_bust(self):
        """玩家爆牌结束"""
        profit = -self.current_bet
        player_total = self.current_hand['player_total']
        
        self.current_hand.update({
            'game_over': True,
            'result_text': "💥 玩家爆牌 - 失败",
            'result': {
                'outcome': 'loss',
                'profit': profit,
                'player_total': player_total,
                'dealer_total': 0
            }
        })
        
        # 添加到历史记录
        self.game_history.append({
            'timestamp': datetime.now(),
            'bet': self.current_bet,
            'player_total': player_total,
            'dealer_total': 0,
            'result': 'loss',
            'profit': profit,
            'player_cards': self.current_hand['player_cards'][:],
            'dealer_cards': self.current_hand['dealer_cards'][:]
        })
    
    def show_hand_result(self):
        """显示本局结果"""
        if not self.current_hand:
            return
        
        result = self.current_hand.get('result', {})
        result_text = self.current_hand.get('result_text', '')
        profit = result.get('profit', 0)
        
        print("\n" + "="*60)
        print("🎊 本局结果")
        print("="*60)
        print(result_text)
        print(f"💰 盈亏: ${profit:+.0f}")
        print(f"💎 当前筹码: ${self.player_chips}")
        print("="*60)
    
    def get_ai_decision(self):
        """获取AI决策"""
        if not self.current_hand:
            return
        
        print("\n🤖 AI正在分析...")
        time.sleep(1)
        
        # 简化的AI决策逻辑
        player_total = self.current_hand['player_total']
        dealer_upcard = self.current_hand['dealer_upcard']
        
        if player_total <= 11:
            action = "要牌 (Hit)"
            reasoning = "点数较低，安全要牌"
            confidence = "高"
        elif player_total >= 17:
            action = "停牌 (Stand)"
            reasoning = "点数较高，避免爆牌"
            confidence = "高"
        elif 12 <= player_total <= 16:
            if dealer_upcard <= 6:
                action = "停牌 (Stand)"
                reasoning = "庄家牌较弱，保守停牌"
                confidence = "中"
            else:
                action = "要牌 (Hit)"
                reasoning = "庄家牌较强，必须要牌"
                confidence = "中"
        else:
            action = "要牌 (Hit)"
            reasoning = "基于基本策略建议要牌"
            confidence = "低"
        
        print("📋 AI建议报告")
        print("-" * 30)
        print(f"🎯 推荐行动: {action}")
        print(f"🧠 分析依据: {reasoning}")
        print(f"📊 信心度: {confidence}")
        print("-" * 30)
        
        adopt = input("是否采用AI建议？(y/n): ").strip().lower()
        if adopt in ['y', 'yes', '是', '']:
            if '要牌' in action:
                self.player_hit()
            elif '停牌' in action:
                self.player_stand()
            elif '加倍' in action:
                if self.current_hand.get('can_double') and self.player_chips >= self.current_bet:
                    self.player_double()
                else:
                    print("⚠️  无法加倍，改为要牌")
                    self.player_hit()
    
    def show_game_report(self):
        """显示游戏报告"""
        if not self.game_history:
            print("\n📊 暂无游戏历史数据")
            return
        
        print("\n" + "="*60)
        print("📊 游戏性能报告")
        print("="*60)
        
        # 基本统计
        total_hands = len(self.game_history)
        wins = len([g for g in self.game_history if g['result'] == 'win'])
        losses = len([g for g in self.game_history if g['result'] == 'loss'])
        pushes = len([g for g in self.game_history if g['result'] == 'push'])
        
        win_rate = wins / total_hands
        total_profit = sum(g['profit'] for g in self.game_history)
        total_wagered = sum(g['bet'] for g in self.game_history)
        roi = (total_profit / total_wagered) if total_wagered > 0 else 0
        
        print(f"🎲 总局数: {total_hands}")
        print(f"🎉 获胜: {wins} ({win_rate:.1%})")
        print(f"😞 失败: {losses} ({losses/total_hands:.1%})")
        print(f"🤝 平局: {pushes} ({pushes/total_hands:.1%})")
        print(f"💰 总盈亏: ${total_profit:+.0f}")
        print(f"📈 投资回报率: {roi:.2%}")
        print(f"💵 平均每局: ${total_profit/total_hands:.2f}")
        
        # 最近5局
        if total_hands >= 5:
            print("\n📋 最近5局:")
            recent = self.game_history[-5:]
            for i, game in enumerate(recent, 1):
                outcome_symbol = {"win": "🎉", "loss": "😞", "push": "🤝"}
                symbol = outcome_symbol.get(game['result'], "❓")
                print(f"  {symbol} 第{total_hands-5+i}局: ${game['profit']:+.0f} "
                      f"({game['player_total']} vs {game['dealer_total']})")
        
        # 失败局分析
        losing_hands = [g for g in self.game_history if g['result'] == 'loss']
        if losing_hands:
            print(f"\n🔍 失败局分析 ({len(losing_hands)}局):")
            bust_count = len([g for g in losing_hands if g['player_total'] > 21])
            if bust_count > 0:
                print(f"  💥 爆牌: {bust_count} 局 ({bust_count/len(losing_hands):.1%})")
                if bust_count/len(losing_hands) > 0.3:
                    print("  💡 建议: 16点以上更保守地要牌")
            
            weak_hands = len([g for g in losing_hands 
                            if g['player_total'] <= 21 and g['player_total'] < g['dealer_total']])
            if weak_hands > 0:
                print(f"  📉 点数不足: {weak_hands} 局")
        
        print("="*60)
        input("按回车返回游戏...")
    
    def show_final_report(self):
        """显示最终报告"""
        print("\n" + "="*60)
        print("🎊 游戏结束 - 最终报告")
        print("="*60)
        
        if self.game_history:
            self.show_game_report()
        else:
            print("未进行任何游戏")
        
        print(f"\n💰 最终筹码: ${self.player_chips}")
        profit_loss = self.player_chips - 300
        if profit_loss > 0:
            print(f"🎉 总盈利: ${profit_loss}")
            print("恭喜！你成功增加了筹码！")
        elif profit_loss < 0:
            print(f"📉 总亏损: ${abs(profit_loss)}")
            print("别灰心，这是学习的一部分！")
        else:
            print("🤝 收支平衡")
            print("不错的表现！")
        
        print("\n感谢使用21点游戏模拟器！")
        print("="*60)
    
    def scan_available_models(self):
        """扫描可用的AI模型"""
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
                        "type": "混合模型",
                        "path": str(model_file),
                        "timestamp": data.get("timestamp", "未知"),
                        "performance": data.get("performance_summary", {}),
                        "description": "数值+LLM混合训练"
                    })
                except Exception:
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
                        "type": "数值模型",
                        "path": str(model_file),
                        "timestamp": data.get("timestamp", "未知"),
                        "performance": data.get("final_performance", {}),
                        "description": "纯数值优化模型"
                    })
                except Exception:
                    continue
        
        return sorted(models, key=lambda x: x['timestamp'], reverse=True)
    
    def check_can_split(self, cards):
        """检查牌是否可以分牌"""
        if len(cards) != 2:
            return False
        return self.get_card_value(cards[0]) == self.get_card_value(cards[1])
    
    # 辅助函数
    def calculate_hand_value(self, cards):
        """计算手牌点数"""
        total = 0
        aces = 0
        
        for card in cards:
            value = self.get_card_value(card)
            if value == 11:  # Ace
                aces += 1
                total += 11
            else:
                total += value
        
        # 处理Ace的软硬转换
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        
        return total
    
    def get_card_value(self, card):
        """获取卡牌数值"""
        if hasattr(card, 'rank'):
            rank = card.rank
        else:
            # 字符串解析
            card_str = str(card)
            if 'Ace' in card_str:
                return 11
            elif any(face in card_str for face in ['Jack', 'Queen', 'King']):
                return 10
            else:
                # 提取数字
                import re
                match = re.search(r'\b(\d+)\b', card_str)
                if match:
                    return int(match.group(1))
                return 10
        
        if rank == 'Ace':
            return 11
        elif rank in ['Jack', 'Queen', 'King']:
            return 10
        else:
            return int(rank)
    
    def parse_card_string(self, card_str):
        """解析卡牌字符串为卡牌对象"""
        # 简化实现，返回一个模拟卡牌对象
        class MockCard:
            def __init__(self, card_str):
                self.card_str = card_str
                if 'Ace' in card_str:
                    self.rank = 'Ace'
                elif 'Jack' in card_str:
                    self.rank = 'Jack'
                elif 'Queen' in card_str:
                    self.rank = 'Queen'
                elif 'King' in card_str:
                    self.rank = 'King'
                else:
                    import re
                    match = re.search(r'\b(\d+)\b', card_str)
                    if match:
                        self.rank = match.group(1)
                    else:
                        self.rank = '10'
        
        return MockCard(card_str)


def main():
    """主函数"""
    try:
        simulator = TerminalBlackjackSimulator()
        simulator.run()
    except KeyboardInterrupt:
        print("\n\n👋 游戏被中断，再见！")
    except Exception as e:
        print(f"\n❌ 游戏出现错误: {e}")
        print("请检查游戏环境和依赖")


if __name__ == "__main__":
    main()
