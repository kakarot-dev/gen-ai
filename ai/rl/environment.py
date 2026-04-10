from __future__ import annotations

import math
import numpy as np
import gymnasium as gym
from gymnasium import spaces

import config as cfg
from simulation.engine import GameEngine
from simulation.entities import Character
from simulation.actions import GameAction, ActionType, MoveDirection
from ai.rl.opponents import RuleBasedBot

GOAL_NAMES = [
    "idle", "chase_target", "melee_attack", "flank_target", "dash_attack",
    "ranged_attack", "find_vantage_point", "maintain_distance", "kite_target",
    "dash_away", "retreat", "heal",
]
GOAL_TO_IDX = {name: i for i, name in enumerate(GOAL_NAMES)}
NUM_GOALS = len(GOAL_NAMES)

ACTION_MAP = []
for jump in (False, True):
    for d in MoveDirection:
        ACTION_MAP.append((ActionType.MOVE, d, jump))
    for d in MoveDirection:
        ACTION_MAP.append((ActionType.SWORD_ATTACK, d, jump))
    for d in MoveDirection:
        ACTION_MAP.append((ActionType.BOW_ATTACK, d, jump))
    for d in MoveDirection:
        ACTION_MAP.append((ActionType.DASH, d, jump))
    ACTION_MAP.append((ActionType.SHIELD, MoveDirection.NONE, jump))
    ACTION_MAP.append((ActionType.NOOP, MoveDirection.NONE, jump))

NUM_ACTIONS = len(ACTION_MAP)

class ArenaEnv(gym.Env):
    

    metadata = {"render_modes": ["human", "rgb_array"]}

    def __init__(self, npc_type: str = "zombie", render_mode: str | None = None,
                 max_steps: int = 1800):
        super().__init__()

        self.npc_type = npc_type
        self.render_mode = render_mode
        self.max_steps = max_steps

        self.obs_size = 30 + NUM_GOALS
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(self.obs_size,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(NUM_ACTIONS)

        self.engine: GameEngine | None = None
        self.agent: Character | None = None
        self.opponent: Character | None = None
        self.opponent_bot: RuleBasedBot | None = None
        self.current_goal: str = "idle"
        self.step_count = 0
        self._prev_agent_health = cfg.MAX_HEALTH
        self._prev_opponent_health = cfg.MAX_HEALTH

    def set_goal(self, goal_name: str):
        self.current_goal = goal_name

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.engine = GameEngine(num_npcs=1)
        self.agent = self.engine.npcs[0]
        self.agent.char_type = self.npc_type
        self.opponent = self.engine.player
        self.opponent_bot = RuleBasedBot(self.opponent)
        self.step_count = 0
        self.current_goal = "idle"
        self._prev_agent_health = cfg.MAX_HEALTH
        self._prev_opponent_health = cfg.MAX_HEALTH
        return self._get_obs(), {}

    def step(self, action: int):
        self.step_count += 1

        action_type, direction, jump = ACTION_MAP[action]
        agent_action = GameAction(action_type, direction, jump=jump)
        opponent_action = self.opponent_bot.decide(self.agent)

        self.engine.step({
            self.agent: agent_action,
            self.opponent: opponent_action,
        })

        reward = self._compute_reward()
        self._prev_agent_health = self.agent.health
        self._prev_opponent_health = self.opponent.health

        terminated = self.engine.done
        truncated = self.step_count >= self.max_steps

        info = {
            "agent_health": self.agent.health,
            "opponent_health": self.opponent.health,
            "agent_alive": self.agent.alive,
            "opponent_alive": self.opponent.alive,
            "goal": self.current_goal,
        }
        return self._get_obs(), reward, terminated, truncated, info

    def _get_obs(self) -> np.ndarray:
        obs = np.zeros(self.obs_size, dtype=np.float32)
        a = self.agent
        o = self.opponent
        aw = self.engine.arena.width
        ah = self.engine.arena.height

        idx = 0
        obs[idx] = (a.x / aw) * 2 - 1;               idx += 1
        obs[idx] = (a.z / ah) * 2 - 1;               idx += 1
        obs[idx] = a.vx / cfg.DASH_SPEED;             idx += 1
        obs[idx] = a.vz / cfg.DASH_SPEED;             idx += 1
        obs[idx] = a.health / cfg.MAX_HEALTH;         idx += 1
        obs[idx] = a.stamina / cfg.MAX_STAMINA;       idx += 1
        obs[idx] = a.facing_dx;                        idx += 1
        obs[idx] = a.facing_dz;                        idx += 1
        obs[idx] = a.sword_cooldown / max(cfg.SWORD_COOLDOWN, 1); idx += 1
        obs[idx] = a.bow_cooldown / max(cfg.BOW_COOLDOWN, 1);     idx += 1
        obs[idx] = a.dash_cooldown / max(cfg.DASH_COOLDOWN, 1);   idx += 1
        obs[idx] = 1.0 if a.shielding else 0.0;       idx += 1
        obs[idx] = 1.0 if a.dash_timer > 0 else 0.0;  idx += 1
        obs[idx] = a.y / 50.0;                         idx += 1
        obs[idx] = 1.0 if a.on_ground else 0.0;        idx += 1

        dx = o.x - a.x
        dz = o.z - a.z
        dist = math.hypot(dx, dz) + 1e-6
        obs[idx] = dx / aw;                            idx += 1
        obs[idx] = dz / ah;                            idx += 1
        obs[idx] = min(dist / 300, 1.0);               idx += 1
        obs[idx] = o.vx / cfg.DASH_SPEED;             idx += 1
        obs[idx] = o.vz / cfg.DASH_SPEED;             idx += 1
        obs[idx] = o.health / cfg.MAX_HEALTH;         idx += 1
        obs[idx] = 1.0 if o.shielding else 0.0;       idx += 1
        obs[idx] = 1.0 if o.alive else 0.0;           idx += 1
        obs[idx] = (o.y - a.y) / 50.0;                 idx += 1

        if dist > 0:
            obs[idx] = (dx * a.facing_dx + dz * a.facing_dz) / dist
        idx += 1

        obs[idx] = a.x / aw;                           idx += 1
        obs[idx] = (aw - a.x) / aw;                    idx += 1
        obs[idx] = a.z / ah;                           idx += 1
        obs[idx] = (ah - a.z) / ah;                    idx += 1

        nearest_dist = 999.0
        nearest_dx, nearest_dz = 0.0, 0.0
        for pickup in self.engine.pickups:
            if pickup.alive:
                pdist = math.hypot(pickup.x - a.x, pickup.z - a.z)
                if pdist < nearest_dist:
                    nearest_dist = pdist
                    nearest_dx = (pickup.x - a.x) / aw
                    nearest_dz = (pickup.z - a.z) / ah

        goal_idx = GOAL_TO_IDX.get(self.current_goal, 0)
        obs[30 + goal_idx] = 1.0

        return obs

    def _compute_reward(self) -> float:
        reward = 0.0

        dmg_dealt = self._prev_opponent_health - self.opponent.health
        if dmg_dealt > 0:
            reward += dmg_dealt * 0.1

        dmg_taken = self._prev_agent_health - self.agent.health
        if dmg_taken > 0:
            reward -= dmg_taken * 0.08

        if not self.opponent.alive:
            reward += 10.0
        if not self.agent.alive:
            reward -= 10.0

        reward += self._goal_reward()
        reward -= 0.001

        return reward

    def _goal_reward(self) -> float:
        a = self.agent
        o = self.opponent
        dist = math.hypot(o.x - a.x, o.z - a.z)

        if self.current_goal in ("chase_target", "melee_attack", "dash_attack"):
            return 0.01 if dist < 60 else -0.002
        elif self.current_goal in ("retreat", "maintain_distance", "dash_away"):
            return 0.01 if dist > 120 else -0.002
        elif self.current_goal in ("ranged_attack", "kite_target"):
            return 0.01 if 80 < dist < 220 else -0.001
        elif self.current_goal == "heal":
            for pickup in self.engine.pickups:
                if pickup.alive:
                    if math.hypot(pickup.x - a.x, pickup.z - a.z) < 30:
                        return 0.05
            return -0.001
        return 0.0

    def render(self):
        pass

    def close(self):
        pass
