# Game Character Behavior Generation using Reinforcement Learning

A hybrid AI system that **generates** intelligent NPC combat behavior by combining
Goal-Oriented Action Planning (GOAP) with a Proximal Policy Optimization (PPO) policy.
Deployed as Mineflayer bots in a live Minecraft 1.21.4 server.

---

## What this project is

Traditional video game NPCs rely on hand-coded rules ("if health < 50% retreat"). This
project replaces those rules with a **trained neural network** that learns WHEN to pick
which strategic goal, based on experience from thousands of simulated fights.

Two role-specific models are trained:

| NPC | Role | Strategy |
|---|---|---|
| **Zombie** | Melee | Aggressive close combat, flank with cover, retreat at critical HP |
| **Skeleton** | Ranged | Maintain distance, kite, find vantage points, break LoS |

The same architecture, observation space, action space, and algorithm produce both.
The only difference is the **reward function** — which is how behavior is "generated"
rather than designed.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Layer 1: AI Brain (Python)              │
│  GOAP Planner · PPO Policy · World State Builder     │
└────────────────────┬────────────────────────────────┘
                     │ HTTP (goal name)
                     ▼
┌─────────────────────────────────────────────────────┐
│           Layer 2: Mineflayer Bridge (Node.js)       │
│   HTTP API · mineflayer-pvp · pathfinder · Cover     │
└────────────────────┬────────────────────────────────┘
                     │ Minecraft protocol
                     ▼
┌─────────────────────────────────────────────────────┐
│         Layer 3: Paper 1.21.4 Minecraft Server       │
│   Custom 50x50 arena · Buildings · Cover · Lava     │
└─────────────────────────────────────────────────────┘
```

- **Python** runs the brain: GOAP planner, PPO policy, decision logic.
- **Node.js** (Mineflayer) runs the body: actual combat, pathfinding, cover-seeking.
- **Paper server** hosts the arena. The player connects with TLauncher 1.21.4.

---

## RL Formulation

**Algorithm**: PPO (Stable-Baselines3) with [128, 128] MLP

**Observation** (17 floats, all normalized 0-1):

| # | Feature |
|---|---|
| 0 | Own health |
| 1 | Own stamina |
| 2 | Distance to target |
| 3-4 | Direction to target (dx, dz) |
| 5 | Target health |
| 6 | In melee range |
| 7 | In bow range |
| 8 | Target too close |
| 9 | Target too far |
| 10 | Low health flag |
| 11 | Previous goal |
| 12 | Time on current goal |
| 13-14 | Recent damage dealt/taken |
| 15 | **Line of sight to target** |
| 16 | **Cover available nearby** |

**Action**: `Discrete(12)` — one of 12 GOAP goals

```
0. idle              6. find_vantage_point
1. chase_target      7. maintain_distance
2. melee_attack      8. kite_target
3. flank_target      9. dash_away
4. dash_attack      10. retreat
5. ranged_attack    11. heal
```

**Reward** (simplified):
- `+0.5 per HP` damage dealt
- `-0.15 per HP` damage taken
- `+30` kill, `-10` death
- `+1.5` damage dealt without line of sight (ambush bonus)
- `+0.8` broke LoS while retreating (used cover)
- `-1.0` passivity (no damage dealt while opponent alive)
- `-2.0` healthy retreat (HP > 35%)
- Role-specific bonuses for appropriate goals

**Decision interval**: every 30 simulation frames (~0.5s game time)

---

## Repository Structure

```
genai/
├── ai/                         # AI brain (Python)
│   ├── goap/                   # GOAP planner, goals, actions
│   └── rl/
│       ├── goal_env.py         # Gymnasium env for PPO training
│       └── opponents.py        # Rule-based training opponent
├── simulation/                 # Fast training environment
│   ├── engine.py               # Game tick loop
│   ├── entities.py             # Character, projectile, pickup
│   ├── arena.py                # Tile map, LoS, cover search
│   └── actions.py              # Action definitions
├── minecraft/                  # Minecraft deployment
│   ├── mc_controller.py        # Python ↔ bridge client
│   ├── bridge/
│   │   ├── server.js           # Mineflayer HTTP API
│   │   ├── arena_builder.js    # Builds the arena in-game
│   │   └── setup_game.js       # Gears up player + NPCs
│   └── server/                 # Paper server files
├── models/                     # Trained PPO checkpoints
├── scripts/
│   ├── start_infra.sh          # Starts server + bridge
│   ├── generate_charts.py      # Creates report charts
│   └── generate_report.py      # Builds PDF report
├── charts/                     # Generated figures
├── config.py                   # Global constants
├── train.py                    # Entry: train RL agent
├── play.py                     # Entry: deploy in Minecraft
├── justfile                    # Task automation
├── FINDINGS.md                 # Experiment iteration log
└── Project_Report.pdf          # Full technical report
```

---

## Setup

**Prerequisites**: Python 3.12, Node.js 18+, Java 17+, TLauncher (or any MC 1.21.4 client)

```bash
# Clone
git clone git@github.com:kakarot-dev/gen-ai.git
cd gen-ai

# Python venv
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt

# Node.js deps for Mineflayer bridge
cd minecraft/bridge && npm install && cd ../..

# (First time only) Download Paper server jar
# Place paper-1.21.4-<build>.jar at minecraft/server/paper.jar
```

---

## Running the project

The project uses [`just`](https://github.com/casey/just) for task automation.

### Full flow

```bash
# Terminal 1: start MC server + bridge together
just infra

# In Minecraft: join localhost:25565 with TLauncher 1.21.4

# Terminal 2: launch AI in one of 3 modes
just play-goap       # Hand-coded GOAP (baseline)
just play-rl         # Trained RL policy
just play-hybrid     # GOAP + RL combined
```

On first run, build the arena:

```bash
just arena     # Builds the 50x50 combat arena in-game (one-time)
```

### Training

```bash
just train-zombie      # 500K steps, ~15 min on CPU
just train-skeleton    # 500K steps, ~15 min on CPU
just train-all         # Both sequentially
```

### Reports

```bash
just charts    # Regenerate all charts from current models
just report    # Rebuild the PDF report
```

---

## How it was built

See **FINDINGS.md** for the full iteration log. Short version:

1. **Iteration 1** — Generic rewards produced identical strategies for both NPCs. Lesson:
   role differentiation needs asymmetric rewards.

2. **Iteration 2** — Role-specific rewards produced distinct strategies but agents refused
   to retreat at low HP. The math made attacking always more profitable.

3. **Iteration 3** — Added critical-HP retreat bonus. Agent learned to spam `heal` 85% of
   the time because "heal" without a healing mechanic just meant running away safely. **Reward hacking #1**.

4. **Iteration 4** — Added passivity whitelist. Agent found an unlisted safe strategy and
   spammed `dash_away` 96% of the time. Over 500 decisions: 0 kills, 0 deaths, no engagement. **Reward hacking #2**.

5. **Iteration 5** — Replaced whitelist with outcome-based penalties (`-1.0` if no damage
   dealt). Agents finally engaged in combat while respecting critical HP retreats.

6. **Iteration 6** — Added line-of-sight + cover awareness. Agent now has the information
   needed to learn tactical positioning.

Two major instances of reward hacking were discovered and documented. All progress came
from reward function engineering, not from PPO hyperparameter tuning.

---

## Key findings

1. Generic rewards collapse role distinctions. Asymmetric reward shaping is required.
2. Reward hacking is the default. Every gap in the reward function is exploited.
3. Defensive goals must be rewarded by outcome, not by goal selection.
4. Passivity must be penalized globally, not per-action.
5. Damage dealt must dominate the reward signal for combat agents.
6. Terminal rewards (kill bonus) shape long-term strategic behavior.
7. Training progress metrics can be misleading — always inspect learned policies.
8. Simulation limitations propagate to learned behavior.

Full details in `FINDINGS.md`.

---

## Technology stack

- **Python 3.12** — AI brain, training pipeline
- **Stable-Baselines3** — PPO implementation
- **PyTorch** — Neural network backend
- **Gymnasium** — RL environment interface
- **Node.js 18** — Mineflayer runtime
- **Mineflayer + mineflayer-pvp + mineflayer-pathfinder** — bot control
- **Express.js** — HTTP bridge API
- **Paper 1.21.4** — Minecraft server
- **matplotlib** + **fpdf2** — Chart & report generation

---

## Report

Full technical report: `Project_Report.pdf` — includes architecture diagrams, training
curves, strategy distributions, reward function analysis, and the full iteration history.

---

## License

MIT
