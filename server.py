#!/usr/bin/env python3
"""
完整的Vue.js 21点模拟器服务器
结合了静态文件服务和API功能
"""
from flask import Flask, jsonify, request, send_from_directory, render_template_string
from flask_cors import CORS
import os
import json
import random
from datetime import datetime

app = Flask(__name__)
CORS(app)

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
        """基本策略决策"""
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
        'active_sessions': len(game_sessions)
    })

@app.route('/api/game/start', methods=['POST'])
def start_game():
    try:
        settings = request.json
        game_id = f"game_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        game_sessions[game_id] = {
            'game': SimpleBlackjackGame(settings.get('numDecks', 1)),
            'chips': settings.get('initialChips', 300),
            'history': [],
            'created': datetime.now()
        }
        
        return jsonify({
            'success': True,
            'game_id': game_id
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
        game = game_sessions[game_id]['game']
        
        decision = game.get_basic_strategy_decision(
            data['player_cards'],
            data['dealer_upcard']
        )
        
        return jsonify({
            'success': True,
            'decision': decision
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
    print("🎮 21点游戏模拟器")
    print("=" * 50)
    print("🌐 游戏地址: http://localhost:8888")
    print("📱 支持桌面和移动设备")
    print("🃏 包含AI助手和统计功能") 
    print("� 访问权限: 仅本机访问")
    print("�🔧 按 Ctrl+C 停止服务器")
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
        print("💡 请确保已安装依赖: pip install flask flask-cors")
