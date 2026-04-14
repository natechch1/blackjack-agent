#!/usr/bin/env python3
"""
完整的Vue.js 21点模拟器服务器
结合了静态文件服务和API功能
支持两种模式：Lite（规则引擎）和 Full（AI Agent + LLM 工具链）
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import sys
import random
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ===== Full Mode Detection =====
# Try to import AI tools from src/; if available, enable Full Mode
FULL_MODE = False
_basic_strategy = None
_monte_carlo = None

try:
    # Ensure project root is on the import path so `src` is a package
    _project_root = os.path.dirname(os.path.abspath(__file__))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    from src.game.cards import Card, Rank, Suit, Hand
    from src.game.blackjack_env import Action
    from src.tools.basic_strategy import BasicStrategy
    from src.tools.card_counting import CardCounter
    from src.tools.monte_carlo import MonteCarloSimulator

    _basic_strategy = BasicStrategy()
    _monte_carlo = MonteCarloSimulator(num_processes=2)
    FULL_MODE = True
except ImportError as e:
    print(f"ℹ️  Lite Mode: AI tools not available ({e})")
except Exception as e:
    print(f"ℹ️  Lite Mode: Failed to initialize AI tools ({e})")


# ===== Card Conversion Helper =====
def _frontend_card_to_src(card_dict):
    """Convert frontend card dict {'rank': 'Ace', 'suit': 'Hearts'} to src Card object"""
    rank_map = {
        'Ace': Rank.ACE, '2': Rank.TWO, '3': Rank.THREE, '4': Rank.FOUR,
        '5': Rank.FIVE, '6': Rank.SIX, '7': Rank.SEVEN, '8': Rank.EIGHT,
        '9': Rank.NINE, '10': Rank.TEN, 'Jack': Rank.JACK,
        'Queen': Rank.QUEEN, 'King': Rank.KING
    }
    suit_map = {
        'Hearts': Suit.HEARTS, 'Diamonds': Suit.DIAMONDS,
        'Clubs': Suit.CLUBS, 'Spades': Suit.SPADES
    }
    return Card(rank=rank_map[card_dict['rank']], suit=suit_map[card_dict['suit']])


def _build_hand_from_cards(card_dicts):
    """Convert a list of frontend card dicts into a src Hand object"""
    hand = Hand()
    for cd in card_dicts:
        hand.add_card(_frontend_card_to_src(cd))
    return hand


def _get_full_decision(player_cards, dealer_upcard, game_session):
    """
    Full Mode decision: uses BasicStrategy tables + CardCounter + MonteCarloSimulator.
    Returns a rich decision dict with action, reasoning, confidence, and tool outputs.
    """
    # Build Hand and Card objects
    player_hand = _build_hand_from_cards(player_cards)
    dealer_card = _frontend_card_to_src(dealer_upcard)

    # Available actions (simplified — assume hit/stand/double)
    available_actions = [Action.HIT, Action.STAND]
    if player_hand.can_double:
        available_actions.append(Action.DOUBLE)

    # 1. Basic Strategy
    bs_action, bs_explanation, bs_confidence = _basic_strategy.get_recommendation(
        player_hand, dealer_card, available_actions
    )

    # 2. Card Counting — update counter with all visible cards
    shoe_info = game_session.get('shoe_info', {})
    num_decks = shoe_info.get('num_decks', 1)

    # Count all cards seen so far in this session
    counter = CardCounter()
    counter.reset_count(num_decks)
    history = game_session.get('history', [])
    for past_hand in history:
        for cd in past_hand.get('player_cards', []):
            try:
                counter.update_count(_frontend_card_to_src(cd))
            except Exception:
                pass
        for cd in past_hand.get('dealer_cards', []):
            try:
                counter.update_count(_frontend_card_to_src(cd))
            except Exception:
                pass
    # Also count current visible cards
    for cd in player_cards:
        try:
            counter.update_count(_frontend_card_to_src(cd))
        except Exception:
            pass
    try:
        counter.update_count(dealer_card)
    except Exception:
        pass

    cards_remaining = num_decks * 52 - counter.cards_seen
    decks_remaining = max(0.5, cards_remaining / 52.0)
    true_count = counter.get_true_count(decks_remaining)
    risk_assessment = counter.get_risk_assessment(true_count, game_session.get('chips', 300))

    # 3. Monte Carlo Simulation (reduced iterations for speed)
    mc_results = {}
    try:
        for action in available_actions[:3]:
            sim_result = _monte_carlo.simulate_hand_outcome(
                player_hand.cards,
                dealer_card,
                num_simulations=500,
                action=action
            )
            mc_results[action.value] = {
                'win_prob': round(sim_result.win_probability * 100, 1),
                'ev': round(sim_result.expected_value, 3)
            }
    except Exception:
        mc_results = None

    # Final action: prefer basic strategy (proven optimal), note MC for reference
    final_action = bs_action.value  # 'hit', 'stand', 'double', etc.

    # Build rich reasoning
    action_zh_map = {'hit': '要牌', 'stand': '停牌', 'double': '加倍', 'split': '分牌', 'surrender': '投降'}
    action_zh = action_zh_map.get(final_action, final_action)

    # Reasoning parts
    reasoning_parts = [f"基本策略: {bs_explanation}"]
    reasoning_parts.append(f"Hi-Lo真实计数: {true_count:.1f} ({risk_assessment})")
    if mc_results:
        mc_summary = ", ".join([f"{k}: EV={v['ev']:.3f} 胜率={v['win_prob']}%" for k, v in mc_results.items()])
        reasoning_parts.append(f"蒙特卡洛模拟: {mc_summary}")

    confidence_zh = '高' if bs_confidence >= 0.9 else ('中' if bs_confidence >= 0.7 else '低')

    return {
        'action': action_zh,
        'reasoning': ' | '.join(reasoning_parts),
        'confidence': confidence_zh,
        'tools_used': {
            'basic_strategy': {
                'action': final_action,
                'explanation': bs_explanation,
                'confidence': round(bs_confidence, 2)
            },
            'card_counting': {
                'running_count': counter.running_count,
                'true_count': round(true_count, 2),
                'cards_seen': counter.cards_seen,
                'risk': risk_assessment
            },
            'monte_carlo': mc_results
        }
    }


# 游戏状态存储
game_sessions = {}

class SimpleBlackjackGame:
    def __init__(self, num_decks=1):
        self.num_decks = num_decks
        self.reset_shoe()

    def reset_shoe(self):
        """重新洗牌"""
        suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        ranks = ['Ace', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King']

        self.cards = []
        for _ in range(self.num_decks):
            for suit in suits:
                for rank in ranks:
                    self.cards.append({'rank': rank, 'suit': suit})

        random.shuffle(self.cards)

    def deal_card(self):
        """发一张牌"""
        if len(self.cards) < 10:
            self.reset_shoe()
        return self.cards.pop()

    def calculate_hand_value(self, cards):
        """计算手牌点数"""
        total = 0
        aces = 0

        for card in cards:
            rank = card['rank']
            if rank == 'Ace':
                aces += 1
                total += 11
            elif rank in ['Jack', 'Queen', 'King']:
                total += 10
            else:
                total += int(rank)

        while total > 21 and aces > 0:
            total -= 10
            aces -= 1

        return total

    def get_basic_strategy_decision(self, player_cards, dealer_upcard):
        """基本策略决策 (Lite Mode fallback)"""
        player_total = self.calculate_hand_value(player_cards)
        dealer_value = self.get_card_value(dealer_upcard)

        if player_total <= 11:
            return {
                'action': '要牌',
                'reasoning': '点数较低，安全要牌',
                'confidence': '高'
            }
        elif player_total >= 17:
            return {
                'action': '停牌',
                'reasoning': '点数较高，避免爆牌',
                'confidence': '高'
            }
        elif 12 <= player_total <= 16:
            if dealer_value <= 6:
                return {
                    'action': '停牌',
                    'reasoning': f'庄家显示{dealer_value}，较弱，保守停牌',
                    'confidence': '中'
                }
            else:
                return {
                    'action': '要牌',
                    'reasoning': f'庄家显示{dealer_value}，较强，必须要牌',
                    'confidence': '中'
                }
        else:
            return {
                'action': '要牌',
                'reasoning': '基于基本策略建议',
                'confidence': '低'
            }

    def get_card_value(self, card):
        """获取卡牌数值"""
        rank = card['rank']
        if rank == 'Ace':
            return 11
        elif rank in ['Jack', 'Queen', 'King']:
            return 10
        else:
            return int(rank)

# 静态文件路由
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

# API路由
@app.route('/api/health')
def health():
    return jsonify({
        'status': 'healthy',
        'version': '1.0',
        'mode': 'full' if FULL_MODE else 'lite',
        'active_sessions': len(game_sessions)
    })

@app.route('/api/mode')
def get_mode():
    """Return current server mode (lite or full)"""
    return jsonify({
        'mode': 'full' if FULL_MODE else 'lite',
        'features': {
            'basic_strategy_tables': FULL_MODE,
            'card_counting': FULL_MODE,
            'monte_carlo': FULL_MODE,
        }
    })

@app.route('/api/game/start', methods=['POST'])
def start_game():
    try:
        settings = request.json
        game_id = f"game_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        num_decks = settings.get('numDecks', 1)
        initial_chips = settings.get('initialChips', 300)

        game_sessions[game_id] = {
            'game': SimpleBlackjackGame(num_decks),
            'chips': initial_chips,
            'history': [],
            'shoe_info': {'num_decks': num_decks},
            'created': datetime.now()
        }

        return jsonify({
            'success': True,
            'game_id': game_id,
            'mode': 'full' if FULL_MODE else 'lite'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/game/<game_id>/decision', methods=['POST'])
def get_decision(game_id):
    try:
        if game_id not in game_sessions:
            return jsonify({'success': False, 'error': 'Game not found'}), 404

        data = request.json
        session = game_sessions[game_id]

        if FULL_MODE:
            # Full Mode: use AI tool chain
            decision = _get_full_decision(
                data['player_cards'],
                data['dealer_upcard'],
                session
            )
        else:
            # Lite Mode: simple rules
            game = session['game']
            decision = game.get_basic_strategy_decision(
                data['player_cards'],
                data['dealer_upcard']
            )

        return jsonify({
            'success': True,
            'decision': decision,
            'mode': 'full' if FULL_MODE else 'lite'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/game/<game_id>/deal', methods=['POST'])
def deal_cards(game_id):
    try:
        if game_id not in game_sessions:
            return jsonify({'success': False, 'error': 'Game not found'}), 404

        game = game_sessions[game_id]['game']

        # 发牌
        player_cards = [game.deal_card(), game.deal_card()]
        dealer_cards = [game.deal_card(), game.deal_card()]

        return jsonify({
            'success': True,
            'player_cards': player_cards,
            'dealer_cards': dealer_cards,
            'player_total': game.calculate_hand_value(player_cards),
            'dealer_upcard_value': game.get_card_value(dealer_cards[0])
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/game/<game_id>/hit', methods=['POST'])
def hit(game_id):
    try:
        if game_id not in game_sessions:
            return jsonify({'success': False, 'error': 'Game not found'}), 404

        game = game_sessions[game_id]['game']
        card = game.deal_card()

        return jsonify({
            'success': True,
            'card': card
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    if FULL_MODE:
        print("✅ Full Mode: AI tools loaded (BasicStrategy + CardCounter + MonteCarloSimulator)")
    mode_label = "🧠 满血版 (Full Mode)" if FULL_MODE else "⚡ 轻量版 (Lite Mode)"
    print(f"🎮 21点游戏模拟器 — {mode_label}")
    print("=" * 50)
    print(f"🌐 游戏地址: http://localhost:8888")
    print(f"📱 支持桌面和移动设备")
    print(f"🃏 {'AI Agent工具链 (BasicStrategy + CardCounter + MonteCarlo)' if FULL_MODE else '规则引擎策略建议'}")
    print("=" * 50)

    # 询问用户是否允许局域网访问
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--public':
        host = '0.0.0.0'
        print("⚠️  开放模式: 局域网用户可以访问")
    else:
        host = '127.0.0.1'
        print("🔐 安全模式: 仅本机可访问")
        print("💡 如需局域网访问，请使用: python3 server.py --public")

    try:
        port = int(os.environ.get('PORT', 8888))
        app.run(host=host, port=port, debug=False)
    except KeyboardInterrupt:
        print("\n🛑 服务器已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        if not FULL_MODE:
            print("💡 请确保已安装依赖: pip install flask flask-cors")
        else:
            print("💡 请确保已安装依赖: pip install -r requirements.txt")
