"""Python controller for Minecraft bots via the Mineflayer HTTP bridge.

Supports 3 modes:
  - goap:   GOAP planner picks goals (hand-crafted rules)
  - rl:     Trained RL model picks goals directly
  - hybrid: GOAP picks strategy, RL refines goal selection
"""
from __future__ import annotations

import math
import numpy as np
import requests

BRIDGE_URL = "http://localhost:3001"

# Same goal list as RL environment
GOAL_NAMES = [
    "idle", "chase_target", "melee_attack", "flank_target", "dash_attack",
    "ranged_attack", "find_vantage_point", "maintain_distance", "kite_target",
    "dash_away", "retreat", "heal",
]


class MCBotClient:
    """HTTP client for a single Mineflayer bot."""

    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self.base = f"{BRIDGE_URL}/bots/{bot_id}"

    def set_goal(self, goal: str):
        requests.post(f"{self.base}/goal", json={"goal": goal}, timeout=1)

    def get_state(self) -> dict:
        resp = requests.get(f"{self.base}/state", timeout=1)
        return resp.json()


class MCGameState:
    """Reads full game state from the bridge."""

    @staticmethod
    def get() -> dict:
        return requests.get(f"{BRIDGE_URL}/state", timeout=1).json()

    @staticmethod
    def spawn_bots():
        return requests.post(f"{BRIDGE_URL}/bots/spawn", timeout=30).json()

    @staticmethod
    def reset():
        return requests.post(f"{BRIDGE_URL}/reset", timeout=5).json()


class MCNPCController:
    """Controls an NPC bot in Minecraft.

    Modes:
        goap:   A* planner with hand-crafted goal priorities
        rl:     Trained PPO model picks action → mapped to goal
        hybrid: GOAP picks goal, RL observation includes it
    """

    def __init__(self, bot_id: str, npc_type: str, mode: str = "goap",
                 model_path: str = None):
        self.bot_id = bot_id
        self.npc_type = npc_type
        self.mode = mode
        self.client = MCBotClient(bot_id)
        self._prev_goal = "idle"
        self._goal_frames = 0

        # GOAP setup (used in goap and hybrid modes)
        if mode in ("goap", "hybrid"):
            from ai.goap.planner import GOAPPlanner
            from ai.goap.goals import get_goals_for_type
            from ai.goap.actions import get_actions_for_type
            self.planner = GOAPPlanner(
                get_actions_for_type(npc_type),
                get_goals_for_type(npc_type),
            )

        # RL setup (used in rl and hybrid modes)
        self.rl_model = None
        if mode in ("rl", "hybrid") and model_path:
            from stable_baselines3 import PPO
            self.rl_model = PPO.load(model_path, device="cpu")
            print(f"  [{bot_id}] Loaded RL model from {model_path}")

    def tick(self, game_state: dict):
        """One decision cycle."""
        bot_state = game_state.get("bots", {}).get(self.bot_id)
        if not bot_state or not bot_state.get("alive", False):
            return

        players = game_state.get("players", {})
        if not players:
            self.client.set_goal("idle")
            return

        target = list(players.values())[0]

        if self.mode == "goap":
            goal = self._goap_decide(bot_state, target)
        elif self.mode == "rl":
            goal = self._rl_decide(bot_state, target)
        elif self.mode == "hybrid":
            goal = self._hybrid_decide(bot_state, target)
        else:
            goal = "idle"

        if goal != self._prev_goal:
            self._prev_goal = goal
            self._goal_frames = 0
        self._goal_frames += 1

        if self._goal_frames > 120:
            if hasattr(self, 'planner'):
                self.planner.advance_step()
            self._goal_frames = 0

        self.client.set_goal(goal)

    def _goap_decide(self, bot_state: dict, target: dict) -> str:
        """GOAP-only: planner picks the goal."""
        ws = self._build_world_state(bot_state, target)
        return self.planner.update(ws)

    def _rl_decide(self, bot_state: dict, target: dict) -> str:
        """RL-only: trained goal-selection model picks the GOAP goal directly."""
        if not self.rl_model:
            return "chase_target"

        obs = self._build_goal_obs(bot_state, target)
        action, _ = self.rl_model.predict(obs, deterministic=True)
        return GOAL_NAMES[int(action)]

    def _hybrid_decide(self, bot_state: dict, target: dict) -> str:
        """Hybrid: GOAP picks strategy, RL refines execution.

        GOAP determines the high-level goal, then the RL model's
        observation includes this goal. The RL model can either
        follow the GOAP suggestion or override it based on what
        it learned in training.
        """
        # GOAP suggests a goal
        ws = self._build_world_state(bot_state, target)
        goap_goal = self.planner.update(ws)

        if not self.rl_model:
            return goap_goal

        # RL sees the state and picks its own goal
        obs = self._build_goal_obs(bot_state, target)
        action, _ = self.rl_model.predict(obs, deterministic=False)
        rl_goal = GOAL_NAMES[int(action)]

        # If RL strongly disagrees (different category), use RL's choice
        # Otherwise follow GOAP
        goap_aggressive = goap_goal in ("chase_target", "melee_attack", "dash_attack", "flank_target")
        rl_aggressive = rl_goal in ("chase_target", "melee_attack", "dash_attack", "flank_target")

        if goap_aggressive != rl_aggressive:
            # RL overrides GOAP — it learned something different
            return rl_goal
        return goap_goal

    def _action_to_goal(self, action: int, bot_state: dict, target: dict) -> str:
        """Map an RL action index to a high-level goal name."""
        from ai.rl.environment import ACTION_MAP
        from simulation.actions import ActionType

        action_type, direction, jump = ACTION_MAP[action]
        bp = bot_state["position"]
        tp = target["position"]
        dist = math.hypot(tp["x"] - bp["x"], tp["z"] - bp["z"])
        health = bot_state.get("health", 20)

        if action_type == ActionType.SWORD_ATTACK:
            if dist > 4:
                return "chase_target"  # need to close distance first
            return "melee_attack"
        elif action_type == ActionType.BOW_ATTACK:
            if dist < 6:
                return "kite_target"  # too close for bow, back up
            return "ranged_attack"
        elif action_type == ActionType.DASH:
            if health < 8:
                return "dash_away"
            return "dash_attack"
        elif action_type == ActionType.SHIELD:
            if health < 10:
                return "retreat"
            return "maintain_distance"
        elif action_type == ActionType.MOVE:
            from simulation.actions import DIRECTION_VECTORS
            dx, dz = DIRECTION_VECTORS[direction]
            tdx = tp["x"] - bp["x"]
            tdz = tp["z"] - bp["z"]
            td = math.hypot(tdx, tdz) + 0.1
            dot = (dx * tdx / td) + (dz * tdz / td)
            if dot > 0.2:
                # Moving toward target
                if dist > 4:
                    return "chase_target"
                return "melee_attack"
            elif dot < -0.2:
                # Moving away
                if health < 10:
                    return "retreat"
                return "maintain_distance"
            else:
                return "flank_target"
        else:
            return "idle"

    def _build_observation(self, bot_state: dict, target: dict,
                           goap_goal: str = "idle") -> np.ndarray:
        """Build RL observation vector from Minecraft state.
        Same format as ai/rl/environment.py (42 floats).
        """
        obs = np.zeros(42, dtype=np.float32)
        bp = bot_state["position"]
        tp = target["position"]

        # Arena dimensions (approx)
        aw, ah = 50 * 32, 50 * 32

        idx = 0
        # Agent state (normalized)
        obs[idx] = (bp["x"] / 50) * 2 - 1;              idx += 1
        obs[idx] = (bp["z"] / 50) * 2 - 1;              idx += 1
        obs[idx] = 0;                                     idx += 1  # vx (not available)
        obs[idx] = 0;                                     idx += 1  # vz
        obs[idx] = bot_state.get("health", 20) / 20;     idx += 1
        obs[idx] = bot_state.get("food", 20) / 20;       idx += 1
        obs[idx] = math.sin(bot_state.get("yaw", 0));    idx += 1  # facing_dx
        obs[idx] = math.cos(bot_state.get("yaw", 0));    idx += 1  # facing_dz
        obs[idx] = 0;                                     idx += 1  # sword_cd
        obs[idx] = 0;                                     idx += 1  # bow_cd
        obs[idx] = 0;                                     idx += 1  # dash_cd
        obs[idx] = 0;                                     idx += 1  # shielding
        obs[idx] = 0;                                     idx += 1  # dash_timer
        obs[idx] = (bp.get("y", -59) + 59) / 50;         idx += 1  # y position
        obs[idx] = 1.0 if bot_state.get("onGround") else 0; idx += 1

        # Opponent state (relative)
        dx = tp["x"] - bp["x"]
        dz = tp["z"] - bp["z"]
        dist = math.hypot(dx, dz) + 1e-6
        obs[idx] = dx / 50;                               idx += 1
        obs[idx] = dz / 50;                               idx += 1
        obs[idx] = min(dist / 30, 1.0);                   idx += 1
        obs[idx] = 0;                                     idx += 1  # target vx
        obs[idx] = 0;                                     idx += 1  # target vz
        obs[idx] = 1.0;                                   idx += 1  # target health (unknown)
        obs[idx] = 0;                                     idx += 1  # target shielding
        obs[idx] = 1.0;                                   idx += 1  # target alive
        obs[idx] = 0;                                     idx += 1  # relative height

        # Facing toward opponent
        yaw = bot_state.get("yaw", 0)
        facing_dx = -math.sin(yaw)
        facing_dz = math.cos(yaw)
        obs[idx] = (dx * facing_dx + dz * facing_dz) / dist if dist > 0 else 0
        idx += 1

        # Wall distances (approximate)
        obs[idx] = (bp["x"] - 200) / 50;                  idx += 1
        obs[idx] = (250 - bp["x"]) / 50;                  idx += 1
        obs[idx] = (bp["z"] - 200) / 50;                  idx += 1
        obs[idx] = (250 - bp["z"]) / 50;                  idx += 1

        # GOAP goal one-hot (last 12 values)
        goal_idx = GOAL_NAMES.index(goap_goal) if goap_goal in GOAL_NAMES else 0
        obs[30 + goal_idx] = 1.0

        return obs

    def _build_goal_obs(self, bot_state: dict, target: dict) -> np.ndarray:
        """Build observation for the goal-selection RL model (15 floats)."""
        obs = np.zeros(15, dtype=np.float32)
        bp = bot_state["position"]
        tp = target["position"]
        dx = tp["x"] - bp["x"]
        dz = tp["z"] - bp["z"]
        dist = math.hypot(dx, dz) + 1e-6

        mc_hp = bot_state.get("health", 20)
        obs[0] = mc_hp / 20  # own health
        obs[1] = bot_state.get("food", 20) / 20  # stamina
        obs[2] = min(dist / 30, 1.0)  # distance (MC blocks, max ~30)
        obs[3] = (dx / dist + 1) / 2  # direction x
        obs[4] = (dz / dist + 1) / 2  # direction z
        obs[5] = 1.0  # target health (unknown, assume full)
        obs[6] = 1.0 if dist < 4 else 0.0  # melee range
        obs[7] = 1.0 if 4 < dist < 25 else 0.0  # bow range
        obs[8] = 1.0 if dist < 4 else 0.0  # too close
        obs[9] = 1.0 if dist > 25 else 0.0  # too far
        obs[10] = 1.0 if mc_hp < 10 else 0.0  # low health
        prev_idx = GOAL_NAMES.index(self._prev_goal) if self._prev_goal in GOAL_NAMES else 0
        obs[11] = prev_idx / len(GOAL_NAMES)  # previous goal
        obs[12] = min(self._goal_frames / 30, 1.0)  # time on goal
        obs[13] = 0.0  # dmg dealt (not tracked in MC)
        obs[14] = 0.0  # dmg taken (not tracked in MC)

        return obs

    def _build_world_state(self, bot_state: dict, target: dict):
        """Build GOAP WorldState from Minecraft state."""
        from ai.goap.world_state import WorldState

        ws = WorldState()
        bp = bot_state["position"]
        tp = target["position"]
        dx = tp["x"] - bp["x"]
        dz = tp["z"] - bp["z"]
        dist = math.hypot(dx, dz)

        mc_health = bot_state.get("health", 20)
        ws.set("alive", bot_state.get("alive", True))
        ws.set("health", mc_health * 5)
        ws.set("stamina", bot_state.get("food", 20) * 5)
        ws.set("low_health", mc_health < 10)
        ws.set("has_stamina", bot_state.get("food", 20) > 6)
        ws.set("target_alive", True)
        ws.set("target_distance", dist)
        ws.set("in_melee_range", dist < 4)
        ws.set("in_bow_range", 5 < dist < 30)
        ws.set("target_too_close", dist < 4)
        ws.set("target_too_far", dist > 30)
        ws.set("has_line_of_sight", True)
        ws.set("facing_target", True)
        ws.set("can_sword", True)
        ws.set("can_bow", True)
        ws.set("can_dash", bot_state.get("food", 20) > 6)
        ws.set("potion_nearby", False)
        ws.set("potion_reachable", False)
        ws.set("target_damaged", False)
        ws.set("safe_distance", dist > 10)
        ws.set("at_vantage_point", False)
        ws.set("healed", False)

        return ws
