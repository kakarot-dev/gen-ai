# GOAP+RL Arena Combat — Minecraft Edition

# ── Infrastructure ──
server:
    cd minecraft/server && bash start.sh

arena:
    cd minecraft/bridge && node arena_builder.js

bridge:
    cd minecraft/bridge && node server.js

# Run server + bridge together (foreground, Ctrl+C stops both)
infra:
    bash scripts/start_infra.sh

# ── Play modes (gear up + start AI) ──
play-goap:
    cd minecraft/bridge && node setup_game.js && cd /home/axel/genai && venv/bin/python play.py --mode goap

play-rl:
    cd minecraft/bridge && node setup_game.js && cd /home/axel/genai && venv/bin/python play.py --mode rl

play-hybrid:
    cd minecraft/bridge && node setup_game.js && cd /home/axel/genai && venv/bin/python play.py --mode hybrid

# Default play = goap
play:
    cd minecraft/bridge && node setup_game.js && cd /home/axel/genai && venv/bin/python play.py --mode goap

# ── Training ──
train-zombie:
    cd /home/axel/genai && venv/bin/python train.py --type goal --npc-type zombie --timesteps 500000

train-skeleton:
    cd /home/axel/genai && venv/bin/python train.py --type goal --npc-type skeleton --timesteps 500000

train-all:
    cd /home/axel/genai && venv/bin/python train.py --type goal --npc-type zombie --timesteps 500000 && \
    venv/bin/python train.py --type goal --npc-type skeleton --timesteps 500000

# ── Charts & Report ──
charts:
    cd /home/axel/genai && venv/bin/python scripts/generate_charts.py

report: charts
    cd /home/axel/genai && venv/bin/python scripts/generate_report.py

# ── Setup ──
setup:
    cd minecraft/bridge && npm install
    pip install -r requirements.txt

# ── Test ──
test:
    cd /home/axel/genai && venv/bin/python -c "from simulation.engine import GameEngine; from ai.rl.goal_env import GoalSelectionEnv; print('All OK')"
