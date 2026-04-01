# GOAP+RL Arena Combat — Minecraft Edition

# ── Infrastructure ──
server:
    cd minecraft/server && bash start.sh

arena:
    cd minecraft/bridge && node arena_builder.js

bridge:
    cd minecraft/bridge && node server.js

# ── Play modes (gear up + start AI) ──
play-goap:
    cd minecraft/bridge && node setup_game.js && cd /home/axel/genai && venv/bin/python play.py --mode goap

play-rl:
    cd minecraft/bridge && node setup_game.js && cd /home/axel/genai && venv/bin/python play.py --mode rl --model models/zombie_goal/best/best_model.zip

play-hybrid:
    cd minecraft/bridge && node setup_game.js && cd /home/axel/genai && venv/bin/python play.py --mode hybrid --model models/zombie_goal/best/best_model.zip

# Default play = goap
play:
    cd minecraft/bridge && node setup_game.js && cd /home/axel/genai && venv/bin/python play.py --mode goap

# ── Training ──
train-zombie:
    cd /home/axel/genai && venv/bin/python train.py --npc-type zombie --timesteps 500000

train-skeleton:
    cd /home/axel/genai && venv/bin/python train.py --npc-type skeleton --timesteps 500000

train-quick:
    cd /home/axel/genai && venv/bin/python train.py --npc-type zombie --timesteps 20000 --n-envs 2

# ── Setup ──
setup:
    cd minecraft/bridge && npm install
    pip install -r requirements.txt

# ── Test ──
test:
    cd /home/axel/genai && venv/bin/python -c "from simulation.engine import GameEngine; from ai.rl.environment import ArenaEnv; print('All OK')"
