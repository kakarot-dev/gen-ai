# Experiment Findings and Iteration Log

This document records the full iteration history of training the goal-selection RL agents,
including the reward-hacking problems encountered and how they were addressed. It is the
honest record of what worked, what failed, and why.

---

## Overview

**Goal**: Train a PPO policy that selects which of 12 GOAP goals (attack, retreat, flank,
heal, kite, etc.) an NPC should pursue, based on game state observations. The decision-making
behavior should emerge from reward signals rather than hand-coded rules.

**Algorithm**: PPO (Stable-Baselines3)
**Observation**: 15-dim vector (health, distance, direction, range flags, etc.)
**Action**: Discrete(12) goals
**Decision interval**: 30 simulation frames between goal choices
**Training steps**: 500,000 per model

---

## Iteration 1 — Generic Rewards (Initial Baseline)

### Reward function
```
+0.15 * damage_dealt
-0.10 * damage_taken
+15.0 kill
-15.0 death
+0.1 alive per decision
+goal-appropriate bonuses (same for both roles)
```

### Result
Both models converged to **reward ~33** after 500K steps. Strategy distribution was similar
for both roles — 88% melee_attack. There was no meaningful role differentiation because the
reward function didn't distinguish between the zombie (melee) and skeleton (ranged).

### What this taught us
A generic reward function collapses two distinct roles into one dominant strategy. Reward
shaping is required to produce specialized behaviors.

---

## Iteration 2 — Role-Specific Rewards

### Changes
Split the reward function into `zombie` and `skeleton` branches:
- Zombie gets bonuses for melee hits and close-range combat, penalties for kiting/ranged
- Skeleton gets bonuses for ranged hits and good distance (80-220), penalties for melee
- Asymmetric retreat rewards — retreat OK when hurt, penalized when healthy

### Result
| Model     | 100K | 200K | 300K | 400K | 500K |
|-----------|------|------|------|------|------|
| Zombie    | 60.3 | 60.3 | 60.3 | 60.8 | **62.5** |
| Skeleton  | 21.8 | 49.2 | 51.9 | 19.5 | **53.3** |

**Learned strategies:**
- Zombie: 94% melee_attack, 3% kite, 2% dash_attack, 1% flank
- Skeleton: 77% find_vantage_point, 9% retreat, 6% kite

### What looked good
Both models were role-appropriate. Rewards ~2x higher than iteration 1. Distinct strategies
emerged per role.

### What was wrong (discovered in live testing)
When tested in Minecraft, the zombie:
- At HP 4/20 (20%), was still choosing melee_attack / kite_target
- Would not retreat even when clearly dying
- The reward balance meant landing hits (+2.0) beat retreating (+1.0) mathematically
- The agent never had to learn retreating because the simulation opponent was too weak

**Lesson**: A model can look good in training metrics while failing to learn important
defensive behaviors if those behaviors don't pay off in expectation.

---

## Iteration 3 — Critical HP Pressure

### Changes
- **+5.0 reward** for retreat/dash_away/heal at HP < 25%
- **-3.0 penalty** for any attack goal at HP < 25%
- Doubled damage-taken penalty (-0.25, was -0.1)
- Death penalty increased (-20, was -15)
- Attack rewards only at healthy HP (> 40%)

### Result
Training rewards shot up to ~500 by 400K steps. Looked like a big win.

### What was actually wrong — REWARD HACKING (Round 1)
Inspection of the learned policy revealed:
```
ZOMBIE strategy:
  heal             85%
  dash_attack       9%
  flank_target      3%
  retreat           2%
  melee_attack      1%
```

The agent learned to **spam the "heal" goal 85% of the time**. Because:
1. At critical HP, heal gave +5.0
2. The rule-based executor for "heal" just moved the agent away from the opponent
3. Moving away = never takes damage = never has to attack
4. Simulation had no actual healing mechanic, but the reward didn't require HP recovery
5. Survival bonus (+0.1 per decision) + no damage taken = infinite positive reward loop

**The agent discovered that healing without actually engaging is a safe positive-reward strategy.**

### Lesson
Rewards based on *actions* rather than *outcomes* are hackable. "Pick the heal goal" was
rewarded, but "actually heal" was not. The agent optimized the easy-to-measure proxy.

---

## Iteration 4 — Anti-Passivity Penalties

### Changes
- Removed the generous critical-HP bonuses (too gameable)
- Added strong **passivity penalty**: -0.3 if goal is passive (idle/heal/find_vantage) and no damage dealt
- Raised damage-dealt reward to 0.3 per HP (was 0.15)
- Raised kill reward to 20 (was 15)
- Death penalty adjusted to -20
- Critical HP: retreat/dash_away gets +3.0, fighting while dying gets -3.0

### Result
Training rewards stayed moderate (~25-27 for zombie, slow climb to ~320 at 400K).

### What was wrong — REWARD HACKING (Round 2)
New strategy:
```
ZOMBIE behavior:
  dash_away         96%
  melee_attack       2%
  retreat            1%
  Kills: 0, Deaths: 0, Damage dealt: 90, Damage taken: 90
```

The agent learned to **spam dash_away 96% of the time**. Because:
1. `dash_away` was not in the "passive" list (only idle/heal/find_vantage were)
2. At critical HP, dash_away gave +3.0
3. So the agent took one hit (dropping HP), then dashed away forever
4. Zero engagement, zero kills, zero deaths — but still positive reward from survival

**Kills: 0, Deaths: 0** over 500 decisions confirmed the agent was completely avoiding combat.

### Lesson
Whitelisting "passive" goals is fragile. The agent found a new safe strategy outside the
whitelist. Retreat-family goals (retreat, dash_away) must be restricted to actual low-HP
situations.

---

## Iteration 5 — Force Engagement

### Changes
- **Damage = everything**: `+0.5 per HP damage dealt` (was 0.3)
- **Kill reward**: 30 (was 20)
- **Global time penalty**: `-1.0 if damage_dealt == 0 AND opponent alive` per decision
- **Extra penalty**: -0.5 if not engaging AND dist > 150
- **Healthy retreat**: -2.0 for retreat/dash_away when HP > 35% (covers both retreat goals)
- **Heal when healthy**: -2.0 if HP > 40%
- **Idle**: -2.0 (never stand still)
- Zombie melee: +0.3 when close, +1.0 when landing hits
- Skeleton ranged: +0.3 at good range (60-220), +1.0 when landing hits

### Math check at HP=20 (full), distance=40
| Action | Reward calculation |
|--------|-------------------|
| melee_attack (hit for 15) | +0.5*15 + 0.3 (close) + 1.0 (hit) = **+8.8** |
| dash_away | -1.0 (passive) - 2.0 (healthy retreat) = **-3.0** |
| idle | -1.0 - 2.0 = **-3.0** |
| heal | -1.0 - 2.0 = **-3.0** |

Attack is now 11 points better than the best alternative. Policy should converge on melee.

### Training results (current run)
| Steps | Zombie Reward |
|-------|--------------|
| 100K  | 47.2         |
| 200K  | 50.0         |
| 300K  | 54.5         |
| (training in progress) |

No evidence of reward hacking yet. The absence of a dominant "safe" strategy means the
agent must actually engage to accumulate reward.

---

## Key Findings Across Iterations

1. **Generic rewards collapse roles**: Two NPC types with the same reward function learn
   the same strategy. Role differentiation requires role-specific reward shaping.

2. **Reward hacking is the default, not the exception**: Every iteration that created a
   "safe" path to positive reward was immediately exploited. The agent always finds the
   laziest strategy that maximizes the numeric signal.

3. **Healing/retreat goals must be conditional on state, not just rewarded categorically**:
   Iteration 3 and 4 both failed because retreat-family goals were rewarded in absolute
   terms rather than relative to actual need.

4. **Passivity must be punished globally, not per-action**: Iteration 4 whitelisted specific
   passive goals but the agent found unlisted safe goals. A global "no damage this window =
   penalty" is more robust.

5. **Damage dealt must dominate**: If defensive rewards exceed offensive rewards, agents
   will always prefer safety. Damage dealt must have the highest weight in the reward
   function for combat agents.

6. **Terminal rewards matter**: Kill reward of 30 provides a strong gradient pull that
   shapes long-term behavior. Without this, agents optimize for per-step reward and avoid
   risky actions that could lead to kills.

7. **Training progress metrics can be misleading**: Iteration 3 showed reward ~500 which
   looked amazing. In reality, the agent had found a degenerate strategy that exploited
   the reward function without any combat behavior.

8. **Simulation limitations propagate**: The simulation has no walls, no real healing
   mechanic, no line-of-sight. Any reward that depends on these mechanics is either
   faked (hackable) or useless. The sim must support the behavior you want to reward.

---

## PPO Hyperparameters (Unchanged Across Iterations)

| Parameter | Value |
|-----------|-------|
| Learning Rate | 3e-4 |
| Batch Size | 64 |
| n_steps | 1024 |
| Epochs per update | 10 |
| Gamma | 0.99 |
| GAE Lambda | 0.95 |
| Clip Range | 0.2 |
| Entropy Coefficient | 0.05 |
| Network | MLP [128, 128], Tanh |
| Parallel Envs | 4 (SubprocVecEnv) |
| Total Timesteps | 500,000 per model |

The hyperparameters were stable across iterations. All the progress came from reward function
engineering, not from tuning PPO itself.

---

## Ongoing Concerns for the Demo

1. **Simulation-to-Minecraft transfer**: The models are trained in a simplified 2D arena.
   Deployment in Minecraft introduces walls, cover, and real combat dynamics the sim lacks.

2. **The agent cannot learn tactical positioning** because the training simulation has no
   walls or cover points. Flanking in the sim is just "move perpendicular" — it doesn't
   mean using buildings for cover like it does in Minecraft.

3. **To get truly tactical behavior** (using walls, line-of-sight, cover), the simulation
   environment would need to be extended to include these features. This is documented as
   future work.
