"""Rule-based bot opponents for training and testing."""
from __future__ import annotations

import math
import random

from simulation.actions import GameAction, ActionType, MoveDirection, DIRECTION_VECTORS
from simulation.entities import Character


def _angle_to_direction(dx: float, dz: float) -> MoveDirection:
    """Convert a (dx, dz) vector to the closest MoveDirection."""
    if dx == 0 and dz == 0:
        return MoveDirection.NONE

    angle = math.atan2(dz, dx)
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


class RuleBasedBot:
    """Simple rule-based NPC for testing and as RL training opponent."""

    def __init__(self, npc: Character):
        self.npc = npc

    def decide(self, target: Character) -> GameAction:
        if not self.npc.alive:
            return GameAction(ActionType.NOOP, MoveDirection.NONE)

        dx = target.x - self.npc.x
        dz = target.z - self.npc.z
        dist = math.hypot(dx, dz)
        direction = _angle_to_direction(dx, dz)

        # Occasionally jump
        should_jump = random.random() < 0.02

        # Retreat if low health
        if self.npc.health < 25 and dist < 100:
            away = _angle_to_direction(-dx, -dz)
            if self.npc.can_dash() and random.random() < 0.3:
                return GameAction(ActionType.DASH, away, jump=should_jump)
            return GameAction(ActionType.MOVE, away, jump=should_jump)

        if self.npc.char_type == "zombie":
            return self._zombie_behavior(target, dx, dz, dist, direction, should_jump)
        elif self.npc.char_type == "skeleton":
            return self._skeleton_behavior(target, dx, dz, dist, direction, should_jump)
        else:
            return self._generic_behavior(target, dx, dz, dist, direction, should_jump)

    def _zombie_behavior(self, target, dx, dz, dist, direction, jump) -> GameAction:
        if dist < 45:
            if self.npc.can_sword():
                return GameAction(ActionType.SWORD_ATTACK, direction, jump=jump)
            perp = _angle_to_direction(-dz, dx)
            return GameAction(ActionType.MOVE, perp)
        elif dist < 120:
            if self.npc.can_dash() and random.random() < 0.15:
                return GameAction(ActionType.DASH, direction, jump=jump)
            return GameAction(ActionType.MOVE, direction, jump=jump)
        else:
            return GameAction(ActionType.MOVE, direction)

    def _skeleton_behavior(self, target, dx, dz, dist, direction, jump) -> GameAction:
        if dist < 60:
            away = _angle_to_direction(-dx, -dz)
            if self.npc.can_dash() and random.random() < 0.2:
                return GameAction(ActionType.DASH, away, jump=jump)
            return GameAction(ActionType.MOVE, away, jump=jump)
        elif dist < 200:
            if self.npc.can_bow():
                return GameAction(ActionType.BOW_ATTACK, direction)
            perp = _angle_to_direction(-dz, dx)
            if random.random() < 0.5:
                perp = _angle_to_direction(dz, -dx)
            return GameAction(ActionType.MOVE, perp)
        else:
            return GameAction(ActionType.MOVE, direction)

    def _generic_behavior(self, target, dx, dz, dist, direction, jump) -> GameAction:
        if dist < 45 and self.npc.can_sword():
            return GameAction(ActionType.SWORD_ATTACK, direction)
        return GameAction(ActionType.MOVE, direction)
