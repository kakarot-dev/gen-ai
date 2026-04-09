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

    def _build_goal_obs(self, bot_state: dict, target: dict) -> np.ndarray:
        """Build observation for the goal-selection RL model (17 floats)."""
        obs = np.zeros(17, dtype=np.float32)
        bp = bot_state["position"]
        tp = target["position"]
        dx = tp["x"] - bp["x"]
        dz = tp["z"] - bp["z"]
        dist = math.hypot(dx, dz) + 1e-6

        mc_hp = bot_state.get("health", 20)
        obs[0] = mc_hp / 20
        obs[1] = bot_state.get("food", 20) / 20
        obs[2] = min(dist / 30, 1.0)
        obs[3] = (dx / dist + 1) / 2
        obs[4] = (dz / dist + 1) / 2
        obs[5] = 1.0  # target health (unknown, assume full)
        obs[6] = 1.0 if dist < 4 else 0.0
        obs[7] = 1.0 if 4 < dist < 25 else 0.0
        obs[8] = 1.0 if dist < 4 else 0.0
        obs[9] = 1.0 if dist > 25 else 0.0
        obs[10] = 1.0 if mc_hp < 10 else 0.0
        prev_idx = GOAL_NAMES.index(self._prev_goal) if self._prev_goal in GOAL_NAMES else 0
        obs[11] = prev_idx / len(GOAL_NAMES)
        obs[12] = min(self._goal_frames / 30, 1.0)
        obs[13] = 0.0
        obs[14] = 0.0
        # LoS: Mineflayer tracks entities that are visible; we assume LoS if dist < 20
        # (bridge would need a raycast for real LoS, simplified here)
        obs[15] = 1.0 if dist < 20 else 0.0
        obs[16] = 1.0  # cover always available in Minecraft arena

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
