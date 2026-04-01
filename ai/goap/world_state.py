"""World state representation for GOAP planning."""
from __future__ import annotations

import math
from simulation.entities import Character, Pickup


class WorldState:
    """A dictionary-like world state that GOAP reasons over.

    Keys are string predicates, values are booleans or numbers.
    The planner checks preconditions against this state and applies effects.
    """

    def __init__(self):
        self.facts: dict[str, bool | float] = {}

    def set(self, key: str, value: bool | float):
        self.facts[key] = value

    def get(self, key: str, default: bool | float = False) -> bool | float:
        return self.facts.get(key, default)

    def matches(self, conditions: dict[str, bool | float]) -> bool:
        """Check if all conditions are satisfied by current state."""
        for key, required in conditions.items():
            actual = self.facts.get(key, False)
            if isinstance(required, bool):
                if bool(actual) != required:
                    return False
            elif isinstance(required, (int, float)):
                if actual < required:
                    return False
        return True

    def apply(self, effects: dict[str, bool | float]) -> WorldState:
        """Return a new WorldState with effects applied."""
        new_state = WorldState()
        new_state.facts = dict(self.facts)
        new_state.facts.update(effects)
        return new_state

    def copy(self) -> WorldState:
        ws = WorldState()
        ws.facts = dict(self.facts)
        return ws

    def __repr__(self):
        return f"WorldState({self.facts})"


def build_world_state(npc: Character, target: Character,
                      all_characters: list[Character],
                      pickups: list[Pickup]) -> WorldState:
    """Build a WorldState from the current game state for an NPC."""
    ws = WorldState()

    dx = target.x - npc.x
    dz = target.z - npc.z
    dist = math.hypot(dx, dz)

    # Self state
    ws.set("alive", npc.alive)
    ws.set("health", npc.health)
    ws.set("stamina", npc.stamina)
    ws.set("low_health", npc.health < 35)
    ws.set("has_stamina", npc.stamina > 25)

    # Relative to target
    ws.set("target_alive", target.alive)
    ws.set("target_distance", dist)
    ws.set("in_melee_range", dist < 50)
    ws.set("in_bow_range", 50 < dist < 250)
    ws.set("target_too_close", dist < 60)
    ws.set("target_too_far", dist > 250)

    # Line of sight (simplified — just check if no wall tiles between)
    ws.set("has_line_of_sight", True)  # TODO: proper raycast

    # Facing target
    if dist > 0:
        dot = (dx * npc.facing_dx + dz * npc.facing_dz) / dist
        ws.set("facing_target", dot > 0.5)
    else:
        ws.set("facing_target", True)

    # Cooldowns
    ws.set("can_sword", npc.can_sword())
    ws.set("can_bow", npc.can_bow())
    ws.set("can_dash", npc.can_dash())

    # Nearby potions
    nearest_potion_dist = float("inf")
    for pickup in pickups:
        if pickup.alive and pickup.pickup_type == "potion":
            pdist = math.hypot(pickup.x - npc.x, pickup.z - npc.z)
            nearest_potion_dist = min(nearest_potion_dist, pdist)
    ws.set("potion_nearby", nearest_potion_dist < 150)
    ws.set("potion_reachable", nearest_potion_dist < 300)

    # Combat state
    ws.set("target_damaged", False)  # effect placeholder
    ws.set("safe_distance", dist > 120)
    ws.set("at_vantage_point", False)  # effect placeholder
    ws.set("healed", False)  # effect placeholder

    return ws
