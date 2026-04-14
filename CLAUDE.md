# Blackjack Agent — Project Summary

## Project Overview

A Blackjack AI Agent that uses a **hybrid approach** combining LLM reasoning with numerical optimization to learn optimal blackjack strategy. The system trains an AI to achieve ~40-45% win rate and positive expected value per hand.

**Core approach:**
- Stage 1: Fast numerical optimization (no LLM, pure simulation)
- Stage 2: LLM fine-tuning with Deepseek R1 via Ollama
- Stage 3: Real game validation

## Tech Stack

| Category | Technology |
|----------|-----------|
| Language | Python 3.9+ |
| AI Agent Framework | LangChain (ReAct pattern) |
| Local LLM | Ollama + Deepseek R1 1.5B (`http://localhost:11434`) |
| Alternative LLMs | llama3:8b, qwen2:7b |
| Web Server | Flask |
| Dashboard | Streamlit |
| Numerical | NumPy 1.24.3, SciPy 1.10.1 |
| Data | Pandas 2.0.3 |
| Charts | Plotly 5.14.1 |
| Validation | Pydantic 2.7.0 |
| Logging | loguru 0.7.0 |
| Config | PyYAML, python-dotenv |

## Project Structure

```
blackjack-agent/
├── src/
│   ├── agent/
│   │   └── blackjack_agent.py    # LLM-powered agent with 6 tools (619 lines)
│   ├── game/
│   │   ├── blackjack_env.py      # Game rules & state management
│   │   └── cards.py              # Card, Hand, Shoe classes
│   ├── tools/
│   │   ├── basic_strategy.py     # Hard/soft/pair strategy tables
│   │   ├── card_counting.py      # Hi-Lo card counting system
│   │   ├── monte_carlo.py        # 10K-iteration outcome simulation
│   │   └── money_management.py   # Kelly criterion bankroll manager
│   ├── training/
│   │   └── self_play.py
│   ├── ui/
│   │   ├── blackjack_simulator.py
│   │   └── dashboard.py
│   └── utils/
│       ├── config.py
│       └── helpers.py
├── config/
│   ├── config.yaml               # Main config (LLM, game rules, bankroll)
│   └── training_config.yaml
├── models/
│   ├── hybrid_training/          # Trained hybrid model JSON files
│   ├── numerical_training/       # Numerical-only model files
│   ├── basic_strategy.json
│   └── overrides.json
├── server.py                     # Flask web server (Lite + Full auto-detect)
├── index.html                    # Vue.js cyberpunk web UI
├── scripts/
│   ├── start_server.py           # One-click launcher (opens browser)
│   ├── train_hybrid.py           # 3-stage training orchestrator
│   ├── train_numerical.py        # Pure numerical optimization
│   ├── play_hybrid.py            # Game player & benchmarker
│   └── play_terminal.py          # Interactive terminal game
├── requirements.txt              # Full Edition dependencies
└── requirements-deploy.txt       # Lite Edition dependencies (Render)
```

## Key Components

### Agent (`src/agent/blackjack_agent.py`)
LangChain ReAct agent with 6 tools:
- `basic_strategy_advisor` — look up strategy tables
- `card_counting_info` — get Hi-Lo true count & bet recommendation
- `monte_carlo_simulation` — simulate hand outcome probabilities
- `betting_advisor` — Kelly criterion bet sizing
- `risk_assessor` — bankroll health & stop conditions
- `game_state_analyzer` — current situation analysis

Falls back to BasicStrategy if LLM is unavailable.

### Game Engine (`src/game/blackjack_env.py`)
- 6-deck shoe, 75% penetration
- Rules: S17 (dealer stands soft 17), 3:2 blackjack, surrender, double after split
- Actions: HIT, STAND, DOUBLE, SPLIT, SURRENDER

### Training Modes (`hybrid_train.py`)
| Mode | Duration | Numerical | LLM | Test |
|------|----------|-----------|-----|------|
| demo | ~3 min | 3K eps | 100 eps | 50 eps |
| standard | ~15 min | 15K eps | 500 eps | 200 eps |
| deep | ~30 min | 50K eps | 2K eps | 1K eps |

## Configuration

**`config/config.yaml`** — primary config:
- LLM: Deepseek R1 1.5B at `localhost:11434`
- Bankroll: $10,000 initial, $25 base bet
- Kelly fraction: 0.25 (conservative)
- Stop-loss: 50%, stop-win: 200%

**`.env`:**
```
OLLAMA_BASE_URL=http://localhost:11434
PYTHONPATH=/path/to/blackjack-agent/src
LOG_LEVEL=INFO
```

## Common Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Prerequisites: Ollama must be running
ollama pull deepseek-r1:1.5b

# Train
python3 scripts/train_hybrid.py --mode demo        # quick test
python3 scripts/train_hybrid.py --mode standard    # recommended
python3 scripts/train_hybrid.py --mode deep        # thorough

# Play
python3 scripts/play_hybrid.py --mode list                      # list trained models
python3 scripts/play_hybrid.py --mode play --rounds 10          # interactive
python3 scripts/play_hybrid.py --mode benchmark --episodes 1000 # benchmark

# Web UI (localhost:8888)
python3 scripts/start_server.py

# Terminal game
python3 scripts/play_terminal.py
```

## Performance Targets

- Win rate: 40-45%
- Average profit per hand: +$0.30 to +$0.50
- Hourly profit: ~$30-50 (100 hands/hr, $25 base bet)
- Trained model size: ~10-50 KB (JSON)
