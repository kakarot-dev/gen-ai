"""RL environment for training GOAP goal selection.

The agent observes the game state and picks which GOAP goal to pursue.
Mineflayer handles execution. This trains the DECISION-MAKING, not movement.

Observation (15 floats):
    - own health (0-1)
    - own food/stamina (0-1)
    - distance to target (0-1, normalized)
    - direction to target (dx, dz normalized)
    - target health (0-1)
    - in melee range (bool)
    - in bow range (bool)
    - target too close (bool)
    - target too far (bool)
    - currently low health (bool)
    - previous goal (one-hot, but simplified to index 0-11 normalized)
    - time on current goal (0-1)
    - damage dealt last window (0-1)
    - damage taken last window (0-1)

Action: Discrete(12) — pick one of 12 GOAP goals
"""
from __future__ import annotations

import math
import numpy as np
import gymnasium as gym
from gymnasium import spaces

import config as cfg
from simulation.engine import GameEngine
from simulation.actions import GameAction, ActionType, MoveDirection
from ai.rl.opponents import RuleBasedBot

GOAL_NAMES = [
    "idle", "chase_target", "melee_attack", "flank_target", "dash_attack",
    "ranged_attack", "find_vantage_point", "maintain_distance", "kite_target",
    "dash_away", "retreat", "heal",
]
NUM_GOALS = len(GOAL_NAMES)


class GoalSelectionEnv(gym.Env):
    """RL environment that trains an agent to pick GOAP goals.

    Every N frames, the agent picks a goal. A rule-based executor
    carries out the goal for N frames. Then the agent observes the
    result and picks again.
    """

    metadata = {"render_modes": []}

    def __init__(self, npc_type: str = "zombie", decision_interval: int = 30,
                 max_decisions: int = 100):
        super().__init__()

        self.npc_type = npc_type
        self.decision_interval = decision_interval  # frames between decisions
        self.max_decisions = max_decisions  # max decisions per episode

        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(15,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(NUM_GOALS)

        self.engine: GameEngine | None = None
        self.agent = None
        self.opponent = None
        self.opponent_bot = None
        self.decision_count = 0
        self.current_goal_idx = 0
        self._prev_agent_hp = cfg.MAX_HEALTH
        self._prev_opp_hp = cfg.MAX_HEALTH
        self._dmg_dealt_window = 0
        self._dmg_taken_window = 0
        self._goal_time = 0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.engine = GameEngine(num_npcs=1)
        self.agent = self.engine.npcs[0]
        self.agent.char_type = self.npc_type
        self.opponent = self.engine.player
        self.opponent_bot = RuleBasedBot(self.opponent)
        self.decision_count = 0
        self.current_goal_idx = 0
        self._prev_agent_hp = cfg.MAX_HEALTH
        self._prev_opp_hp = cfg.MAX_HEALTH
        self._dmg_dealt_window = 0
        self._dmg_taken_window = 0
        self._goal_time = 0
        return self._get_obs(), {}

    def step(self, action: int):
        """Pick a goal, execute it for N frames, return result."""
        self.decision_count += 1
        self.current_goal_idx = action
        goal_name = GOAL_NAMES[action]

        # Record HP before execution
        hp_before = self.agent.health
        opp_hp_before = self.opponent.health

        # Execute the goal for decision_interval frames
        for _ in range(self.decision_interval):
            if self.engine.done:
                break

            # Agent acts based on goal (rule-based executor)
            agent_action = self._execute_goal(goal_name)
            opp_action = self.opponent_bot.decide(self.agent)

            self.engine.step({
                self.agent: agent_action,
                self.opponent: opp_action,
            })

        # Calculate what happened during this decision window
        dmg_dealt = max(0, opp_hp_before - self.opponent.health)
        dmg_taken = max(0, hp_before - self.agent.health)
        self._dmg_dealt_window = dmg_dealt
        self._dmg_taken_window = dmg_taken

        # Reward
        reward = self._compute_reward(dmg_dealt, dmg_taken)

        # Track
        self._prev_agent_hp = self.agent.health
        self._prev_opp_hp = self.opponent.health
        self._goal_time = 0

        terminated = self.engine.done
        truncated = self.decision_count >= self.max_decisions

        info = {
            "goal": goal_name,
            "agent_hp": self.agent.health,
            "opp_hp": self.opponent.health,
            "dmg_dealt": dmg_dealt,
            "dmg_taken": dmg_taken,
        }

        return self._get_obs(), reward, terminated, truncated, info

    def _get_obs(self) -> np.ndarray:
        obs = np.zeros(15, dtype=np.float32)
        a = self.agent
        o = self.opponent

        dist = a.distance_to(o)
        dx = o.x - a.x
        dz = o.z - a.z
        d = math.hypot(dx, dz) + 1e-6

        obs[0] = a.health / cfg.MAX_HEALTH
        obs[1] = a.stamina / cfg.MAX_STAMINA
        obs[2] = min(dist / 300, 1.0)
        obs[3] = (dx / d + 1) / 2  # normalize to 0-1
        obs[4] = (dz / d + 1) / 2
        obs[5] = o.health / cfg.MAX_HEALTH
        obs[6] = 1.0 if dist < 50 else 0.0   # melee range
        obs[7] = 1.0 if 50 < dist < 250 else 0.0  # bow range
        obs[8] = 1.0 if dist < 60 else 0.0   # too close
        obs[9] = 1.0 if dist > 250 else 0.0  # too far
        obs[10] = 1.0 if a.health < 35 else 0.0  # low health
        obs[11] = self.current_goal_idx / NUM_GOALS  # previous goal
        obs[12] = min(self._goal_time / self.decision_interval, 1.0)
        obs[13] = min(self._dmg_dealt_window / 30, 1.0)  # recent damage dealt
        obs[14] = min(self._dmg_taken_window / 30, 1.0)  # recent damage taken

        return obs

    def _compute_reward(self, dmg_dealt: float, dmg_taken: float) -> float:
        reward = 0.0

        # Core combat rewards
        reward += dmg_dealt * 0.15
        reward -= dmg_taken * 0.1

        if not self.opponent.alive:
            reward += 15.0
        if not self.agent.alive:
            reward -= 15.0
        if self.agent.alive:
            reward += 0.1

        goal = GOAL_NAMES[self.current_goal_idx]
        dist = self.agent.distance_to(self.opponent)
        health_pct = self.agent.health / cfg.MAX_HEALTH

        # ── Role-specific rewards ──
        if self.npc_type == "zombie":
            # ZOMBIE: rewarded for closing distance, melee combat, flanking
            if goal in ("chase_target", "melee_attack", "dash_attack", "flank_target"):
                if dmg_dealt > 0:
                    reward += 2.0  # big bonus for landing melee hits
                if dist < 50:
                    reward += 0.5  # good — you're close
                elif dist < 100:
                    reward += 0.2  # ok — getting closer
                else:
                    reward -= 0.2  # too far for melee

            elif goal == "flank_target":
                reward += 0.3  # flanking is smart for melee

            elif goal in ("retreat", "dash_away"):
                if health_pct < 0.25:
                    reward += 1.0  # critical HP, smart to retreat
                elif health_pct < 0.4:
                    reward += 0.3  # hurt, ok to retreat
                else:
                    reward -= 1.0  # healthy zombie retreating = BAD

            elif goal in ("ranged_attack", "kite_target", "maintain_distance"):
                reward -= 0.5  # zombie should NOT be kiting

            elif goal == "heal":
                if health_pct < 0.3:
                    reward += 0.5
                else:
                    reward -= 0.3

        elif self.npc_type == "skeleton":
            # SKELETON: rewarded for keeping distance, ranged attacks, kiting
            if goal in ("ranged_attack", "kite_target", "maintain_distance"):
                if dmg_dealt > 0:
                    reward += 2.0  # ranged hit = great
                if 80 < dist < 220:
                    reward += 0.5  # perfect range
                elif dist < 50:
                    reward -= 0.5  # too close for skeleton

            elif goal == "find_vantage_point":
                reward += 0.3  # repositioning is smart

            elif goal in ("chase_target", "melee_attack", "dash_attack"):
                if dist > 80:
                    reward -= 0.5  # skeleton shouldn't melee from far
                elif dmg_dealt > 0:
                    reward += 0.5  # close range hit, ok

            elif goal in ("retreat", "dash_away"):
                if health_pct < 0.4 or dist < 50:
                    reward += 0.5  # retreating when close/hurt = smart
                else:
                    reward -= 0.3

        return reward

    def _execute_goal(self, goal_name: str) -> GameAction:
        """Rule-based execution of a goal (same as npc_controller)."""
        a = self.agent
        o = self.opponent
        dx = o.x - a.x
        dz = o.z - a.z
        dist = math.hypot(dx, dz)

        # Direction toward target
        angle = math.atan2(dz, dx)
        deg = math.degrees(angle) % 360
        if deg < 22.5 or deg >= 337.5:
            toward = MoveDirection.RIGHT
        elif deg < 67.5:
            toward = MoveDirection.DOWN_RIGHT
        elif deg < 112.5:
            toward = MoveDirection.DOWN
        elif deg < 157.5:
            toward = MoveDirection.DOWN_LEFT
        elif deg < 202.5:
            toward = MoveDirection.LEFT
        elif deg < 247.5:
            toward = MoveDirection.UP_LEFT
        elif deg < 292.5:
            toward = MoveDirection.UP
        else:
            toward = MoveDirection.UP_RIGHT

        # Away
        away_angle = math.atan2(-dz, -dx)
        adeg = math.degrees(away_angle) % 360
        if adeg < 22.5 or adeg >= 337.5:
            away = MoveDirection.RIGHT
        elif adeg < 67.5:
            away = MoveDirection.DOWN_RIGHT
        elif adeg < 112.5:
            away = MoveDirection.DOWN
        elif adeg < 157.5:
            away = MoveDirection.DOWN_LEFT
        elif adeg < 202.5:
            away = MoveDirection.LEFT
        elif adeg < 247.5:
            away = MoveDirection.UP_LEFT
        elif adeg < 292.5:
            away = MoveDirection.UP
        else:
            away = MoveDirection.UP_RIGHT

        if goal_name == "chase_target":
            return GameAction(ActionType.MOVE, toward)
        elif goal_name == "melee_attack":
            if a.can_sword() and dist < 50:
                return GameAction(ActionType.SWORD_ATTACK, toward)
            return GameAction(ActionType.MOVE, toward)
        elif goal_name == "dash_attack":
            if a.can_dash():
                return GameAction(ActionType.DASH, toward)
            return GameAction(ActionType.MOVE, toward)
        elif goal_name == "flank_target":
            perp_angle = math.atan2(dx, -dz)  # perpendicular
            pdeg = math.degrees(perp_angle) % 360
            if pdeg < 45 or pdeg >= 315: perp = MoveDirection.RIGHT
            elif pdeg < 135: perp = MoveDirection.DOWN
            elif pdeg < 225: perp = MoveDirection.LEFT
            else: perp = MoveDirection.UP
            return GameAction(ActionType.MOVE, perp)
        elif goal_name == "ranged_attack":
            if a.can_bow():
                return GameAction(ActionType.BOW_ATTACK, toward)
            return GameAction(ActionType.MOVE, toward)
        elif goal_name in ("maintain_distance", "kite_target"):
            if dist < 80:
                return GameAction(ActionType.MOVE, away)
            elif dist > 200:
                return GameAction(ActionType.MOVE, toward)
            return GameAction(ActionType.BOW_ATTACK, toward) if a.can_bow() else GameAction(ActionType.MOVE, toward)
        elif goal_name in ("retreat", "dash_away"):
            if a.can_dash():
                return GameAction(ActionType.DASH, away)
            return GameAction(ActionType.MOVE, away)
        elif goal_name == "heal":
            return GameAction(ActionType.MOVE, away)
        elif goal_name == "find_vantage_point":
            return GameAction(ActionType.MOVE, away)
        else:
            return GameAction(ActionType.NOOP, MoveDirection.NONE)
