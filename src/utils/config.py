"""
配置管理工具
"""
import yaml
import os
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"配置文件 {config_path} 不存在，使用默认配置")
        return get_default_config()
    except Exception as e:
        print(f"加载配置文件失败: {e}，使用默认配置")
        return get_default_config()


def get_default_config() -> Dict[str, Any]:
    """获取默认配置"""
    return {
        "llm": {
            "model": "deepseek-r1:1.5b",
            "base_url": "http://localhost:11434",
            "temperature": 0.1,
            "max_tokens": 2048
        },
        "game": {
            "num_decks": 6,
            "penetration": 0.75,
            "dealer_hits_soft_17": False,
            "blackjack_pays": 1.5
        },
        "bankroll": {
            "initial_bankroll": 10000,
            "base_bet": 25,
            "kelly_fraction": 0.25
        },
        "training": {
            "self_play_episodes": 50000,
            "optimization_rounds": 10
        }
    }


def save_config(config: Dict[str, Any], config_path: str = "config/config.yaml"):
    """保存配置文件"""
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    except Exception as e:
        print(f"保存配置文件失败: {e}")
