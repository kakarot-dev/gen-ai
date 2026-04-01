"""NPC Controller — bridges GOAP planner with RL policy execution."""
from __future__ import annotations

import math

from simulation.entities import Character, Pickup
from simulation.actions import GameAction, ActionType, MoveDirection, DIRECTION_VECTORS
from ai.goap.planner import GOAPPlanner
from ai.goap.goals import get_goals_for_type
from ai.goap.actions import get_actions_for_type, GOAPAction
from ai.goap.world_state import build_world_state


def _angle_to_direction(dx: float, dy: float) -> MoveDirection:
    """Convert a vector to closest MoveDirection."""
    if abs(dx) < 0.01 and abs(dy) < 0.01:
        return MoveDirection.NONE
    angle = math.atan2(dy, dx)
    deg = math.degrees(angle) % 360
    if deg < 22.5 or deg >= 337.5:
        return MoveDirection.RIGHT
    elif deg < 67.5:
        return MoveDirection.DOWN_RIGHT
    elif deg < 112.5:
        return MoveDirection.DOWN
    elif deg < 157.5:
        return MoveDirection.DOWN_LEFT
    elif deg < 202.5:
        return MoveDirection.LEFT
    elif deg < 247.5:
        return MoveDirection.UP_LEFT
    elif deg < 292.5:
        return MoveDirection.UP
    else:
        return MoveDirection.UP_RIGHT


class NPCController:
    """High-level NPC controller: GOAP plans strategy, execution layer handles actions.

    When an RL model is loaded, the RL policy handles low-level execution.
    Without RL, a rule-based fallback executes GOAP goals.
    """

    def __init__(self, npc: Character, rl_model=None):
        self.npc = npc
        self.rl_model = rl_model

        # GOAP setup
        actions = get_actions_for_type(npc.char_type)
        goals = get_goals_for_type(npc.char_type)
        self.planner = GOAPPlanner(actions, goals)

        # For goal completion detection
        self._prev_goal_action = "idle"
        self._goal_frames = 0
        self._max_goal_frames = 120  # switch after 2 seconds at 60fps

    def decide(self, target: Character, all_characters: list[Character],
               pickups: list[Pickup]) -> GameAction:
        """Decide an action for this frame."""
        if not self.npc.alive:
            return GameAction(ActionType.NOOP, MoveDirection.NONE)

        # Build world state for GOAP
        world_state = build_world_state(self.npc, target, all_characters, pickups)

        # GOAP decides the high-level goal/action
        goal_action_name = self.planner.update(world_state)

        # Track how long we've been on this goal
        if goal_action_name != self._prev_goal_action:
            self._prev_goal_action = goal_action_name
            self._goal_frames = 0
        self._goal_frames += 1

        # If stuck on same goal too long, force replan
        if self._goal_frames > self._max_goal_frames:
            self.planner.advance_step()
            self._goal_frames = 0

        # Execute the goal
        if self.rl_model is not None:
            return self._rl_execute(goal_action_name, target, world_state)
        else:
            return self._rule_execute(goal_action_name, target)

    def _rl_execute(self, goal_name: str, target: Character,
                    world_state) -> GameAction:
        """Use RL model to execute the current GOAP goal.

        The observation includes the goal name as a one-hot vector,
        so the same model handles all goals.
        """
        # This will be implemented when RL training is ready
        # For now fall back to rules
        return self._rule_execute(goal_name, target)

    def _rule_execute(self, goal_name: str, target: Character) -> GameAction:
        """Rule-based execution of GOAP goals (fallback without RL)."""
        dx = target.x - self.npc.x
        dz = target.z - self.npc.z
        dist = math.hypot(dx, dz)
        toward = _angle_to_direction(dx, dz)
        away = _angle_to_direction(-dx, -dz)
        perp = _angle_to_direction(-dz, dx)

        if goal_name == "chase_target":
            return GameAction(ActionType.MOVE, toward)

        elif goal_name == "melee_attack":
            if self.npc.can_sword() and dist < 50:
                return GameAction(ActionType.SWORD_ATTACK, toward)
            return GameAction(ActionType.MOVE, toward)

        elif goal_name == "flank_target":
            # Move perpendicular to get around target
            return GameAction(ActionType.MOVE, perp)

        elif goal_name == "dash_attack":
            if self.npc.can_dash():
                return GameAction(ActionType.DASH, toward)
            return GameAction(ActionType.MOVE, toward)

        elif goal_name == "ranged_attack":
            if self.npc.can_bow():
                return GameAction(ActionType.BOW_ATTACK, toward)
            return GameAction(ActionType.MOVE, perp)  # strafe while on cooldown

        elif goal_name == "find_vantage_point":
            # Move to get good range
            if dist < 80:
                return GameAction(ActionType.MOVE, away)
            elif dist > 220:
                return GameAction(ActionType.MOVE, toward)
            return GameAction(ActionType.MOVE, perp)

        elif goal_name == "maintain_distance":
            return GameAction(ActionType.MOVE, away)

        elif goal_name == "kite_target":
            # Shoot while backing away
            if self.npc.can_bow():
                return GameAction(ActionType.BOW_ATTACK, away)
            return GameAction(ActionType.MOVE, away)

        elif goal_name == "dash_away":
            if self.npc.can_dash():
                return GameAction(ActionType.DASH, away)
            return GameAction(ActionType.MOVE, away)

        elif goal_name == "retreat":
            return GameAction(ActionType.MOVE, away)

        elif goal_name == "heal":
            # TODO: move toward nearest potion
            return GameAction(ActionType.MOVE, away)

        else:  # idle or unknown
            return GameAction(ActionType.NOOP, MoveDirection.NONE)
