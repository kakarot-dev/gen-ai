"""RL environment for training GOAP goal selection with tactical awareness.

The agent observes the game state (including line-of-sight and cover info)
and picks which GOAP goal to pursue.

Observation (17 floats):
    0  own health (0-1)
    1  own stamina (0-1)
    2  distance to target (0-1)
    3  direction dx (0-1)
    4  direction dz (0-1)
    5  target health (0-1)
    6  in melee range
    7  in bow range
    8  target too close
    9  target too far
    10 low health
    11 previous goal (0-1)
    12 time on current goal (0-1)
    13 damage dealt last window (0-1)
    14 damage taken last window (0-1)
    15 line-of-sight to target (bool)
    16 cover available nearby (bool)

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
            low=0.0, high=1.0, shape=(17,), dtype=np.float32
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

    def _has_los(self) -> bool:
        return self.engine.arena.has_line_of_sight(
            self.agent.x, self.agent.z, self.opponent.x, self.opponent.z)

    def _cover_nearby(self) -> bool:
        cover = self.engine.arena.nearest_cover(
            self.agent.x, self.agent.z, self.opponent.x, self.opponent.z)
        return cover is not None

    def _get_obs(self) -> np.ndarray:
        obs = np.zeros(17, dtype=np.float32)
        a = self.agent
        o = self.opponent

        dist = a.distance_to(o)
        dx = o.x - a.x
        dz = o.z - a.z
        d = math.hypot(dx, dz) + 1e-6

        obs[0] = a.health / cfg.MAX_HEALTH
        obs[1] = a.stamina / cfg.MAX_STAMINA
        obs[2] = min(dist / 300, 1.0)
        obs[3] = (dx / d + 1) / 2
        obs[4] = (dz / d + 1) / 2
        obs[5] = o.health / cfg.MAX_HEALTH
        obs[6] = 1.0 if dist < 50 else 0.0
        obs[7] = 1.0 if 50 < dist < 250 else 0.0
        obs[8] = 1.0 if dist < 60 else 0.0
        obs[9] = 1.0 if dist > 250 else 0.0
        obs[10] = 1.0 if a.health < 35 else 0.0
        obs[11] = self.current_goal_idx / NUM_GOALS
        obs[12] = min(self._goal_time / self.decision_interval, 1.0)
        obs[13] = min(self._dmg_dealt_window / 30, 1.0)
        obs[14] = min(self._dmg_taken_window / 30, 1.0)
        obs[15] = 1.0 if self._has_los() else 0.0
        obs[16] = 1.0 if self._cover_nearby() else 0.0

        return obs

    def _compute_reward(self, dmg_dealt: float, dmg_taken: float) -> float:
        """Balanced reward: rewards engagement AND tactical cover use."""
        reward = 0.0

        # Damage is the primary signal — boosted
        reward += dmg_dealt * 0.8       # each HP damage = +0.8
        reward -= dmg_taken * 0.1       # softer penalty

        # Terminal rewards
        if not self.opponent.alive:
            reward += 25.0
        if not self.agent.alive:
            reward -= 8.0

        goal = GOAL_NAMES[self.current_goal_idx]
        dist = self.agent.distance_to(self.opponent)
        health_pct = self.agent.health / cfg.MAX_HEALTH

        # ── Tactical bonuses — all conditional on actual combat ──
        has_los = self._has_los()

        # Ambush: dealt damage while opponent couldn't see us (only if dmg > 0)
        if dmg_dealt > 0 and not has_los:
            reward += 2.5

        # Successful disengagement: ONLY if you actually took damage recently
        # (so we know you're under pressure and need to hide)
        if not has_los and goal in ("retreat", "dash_away") and dmg_taken > 0:
            reward += 1.0

        # Moved toward cover when hurt — requires hurt state
        if health_pct < 0.35 and goal in ("flank_target", "retreat", "find_vantage_point"):
            reward += 0.3

        # ── STRONG anti-passivity ──
        # If you didn't engage and opponent is alive, you're wasting time
        if dmg_dealt == 0 and self.opponent.alive:
            reward -= 0.8
            if dist > 150:
                reward -= 0.5

        # No free reward for picking "tactical" goals while not engaging
        # Passive loop detection: if you keep picking the same goal and dealing no damage
        if dmg_dealt == 0 and goal in ("flank_target", "find_vantage_point"):
            reward -= 0.5  # can't just spam tactical goals

        # Retreating when healthy costs
        if goal in ("dash_away", "retreat") and health_pct > 0.5:
            reward -= 1.0

        # ── Role-specific rewards ──
        if self.npc_type == "zombie":
            # ZOMBIE: melee-focused with tactical flanking
            if goal in ("chase_target", "melee_attack", "dash_attack"):
                if dist < 50:
                    reward += 0.5
                elif dist < 100:
                    reward += 0.2
                else:
                    reward -= 0.2
                if dmg_dealt > 0:
                    reward += 1.5

            elif goal == "flank_target":
                # Only rewarded if it leads to damage or you're actually under threat
                if dmg_dealt > 0:
                    reward += 0.8  # flank that landed hits = great
                elif dist < 60 and dmg_taken == 0:
                    reward += 0.2  # repositioning at close range
                else:
                    reward -= 0.3  # otherwise passive

            elif goal in ("retreat", "dash_away"):
                if health_pct < 0.2:
                    reward += 2.0
                elif health_pct < 0.4 and dmg_taken > 0:
                    reward += 0.5

            elif goal in ("ranged_attack", "kite_target", "maintain_distance"):
                reward -= 1.2  # wrong role

            elif goal == "heal":
                if health_pct < 0.3:
                    reward += 0.5
                elif health_pct > 0.5:
                    reward -= 1.0

            elif goal == "find_vantage_point":
                reward -= 0.5

            elif goal == "idle":
                reward -= 1.0

        elif self.npc_type == "skeleton":
            # SKELETON: keep range AND deal damage
            if goal in ("ranged_attack", "kite_target"):
                if 60 < dist < 220:
                    reward += 0.5
                elif dist < 40:
                    reward -= 0.4
                if dmg_dealt > 0:
                    reward += 1.5

            elif goal == "maintain_distance":
                if 60 < dist < 220:
                    reward += 0.2

            elif goal == "find_vantage_point":
                if dmg_dealt > 0:
                    reward += 0.8  # rewarded for hits from vantage
                elif dist < 40:
                    reward += 0.3  # repositioning when too close
                else:
                    reward -= 0.3  # otherwise passive

            elif goal == "flank_target":
                if dmg_dealt > 0:
                    reward += 0.5
                else:
                    reward -= 0.3

            elif goal in ("chase_target", "melee_attack", "dash_attack"):
                if dist > 80:
                    reward -= 0.8
                elif dmg_dealt > 0:
                    reward += 0.5

            elif goal in ("retreat", "dash_away"):
                if health_pct < 0.3 or dist < 30:
                    reward += 0.8

            elif goal == "heal":
                if health_pct < 0.3:
                    reward += 0.5
                elif health_pct > 0.5:
                    reward -= 1.0

            elif goal == "idle":
                reward -= 1.0

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
            # Try to move to a cover point that breaks LoS first
            cover = self.engine.arena.nearest_cover(a.x, a.z, o.x, o.z)
            if cover is not None:
                cdx = cover[0] - a.x
                cdz = cover[1] - a.z
                return GameAction(ActionType.MOVE, self._dir_from_vec(cdx, cdz))
            # Fallback: perpendicular
            perp_angle = math.atan2(dx, -dz)
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
            # Retreat toward cover if available
            cover = self.engine.arena.nearest_cover(a.x, a.z, o.x, o.z)
            if cover is not None:
                cdx = cover[0] - a.x
                cdz = cover[1] - a.z
                retreat_dir = self._dir_from_vec(cdx, cdz)
            else:
                retreat_dir = away
            if goal_name == "dash_away" and a.can_dash():
                return GameAction(ActionType.DASH, retreat_dir)
            return GameAction(ActionType.MOVE, retreat_dir)
        elif goal_name == "heal":
            # Move toward cover while healing
            cover = self.engine.arena.nearest_cover(a.x, a.z, o.x, o.z)
            if cover is not None:
                cdx = cover[0] - a.x
                cdz = cover[1] - a.z
                return GameAction(ActionType.MOVE, self._dir_from_vec(cdx, cdz))
            return GameAction(ActionType.MOVE, away)
        elif goal_name == "find_vantage_point":
            # Move to a cover point with good firing angle
            cover = self.engine.arena.nearest_cover(a.x, a.z, o.x, o.z)
            if cover is not None:
                cdx = cover[0] - a.x
                cdz = cover[1] - a.z
                return GameAction(ActionType.MOVE, self._dir_from_vec(cdx, cdz))
            return GameAction(ActionType.MOVE, away)
        else:
            return GameAction(ActionType.NOOP, MoveDirection.NONE)

    def _dir_from_vec(self, dx: float, dz: float) -> MoveDirection:
        """Convert a (dx, dz) vector to the closest MoveDirection."""
        if abs(dx) < 0.1 and abs(dz) < 0.1:
            return MoveDirection.NONE
        angle = math.atan2(dz, dx)
        deg = math.degrees(angle) % 360
        if deg < 22.5 or deg >= 337.5: return MoveDirection.RIGHT
        elif deg < 67.5: return MoveDirection.DOWN_RIGHT
        elif deg < 112.5: return MoveDirection.DOWN
        elif deg < 157.5: return MoveDirection.DOWN_LEFT
        elif deg < 202.5: return MoveDirection.LEFT
        elif deg < 247.5: return MoveDirection.UP_LEFT
        elif deg < 292.5: return MoveDirection.UP
        else: return MoveDirection.UP_RIGHT
