from __future__ import annotations

import math
from simulation.entities import Character, Pickup

class WorldState:
    

    def __init__(self):
        self.facts: dict[str, bool | float] = {}

    def set(self, key: str, value: bool | float):
        self.facts[key] = value

    def get(self, key: str, default: bool | float = False) -> bool | float:
        return self.facts.get(key, default)

    def matches(self, conditions: dict[str, bool | float]) -> bool:
        
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
    
    ws = WorldState()

    dx = target.x - npc.x
    dz = target.z - npc.z
    dist = math.hypot(dx, dz)

    ws.set("alive", npc.alive)
    ws.set("health", npc.health)
    ws.set("stamina", npc.stamina)
    ws.set("low_health", npc.health < 35)
    ws.set("has_stamina", npc.stamina > 25)

    ws.set("target_alive", target.alive)
    ws.set("target_distance", dist)
    ws.set("in_melee_range", dist < 50)
    ws.set("in_bow_range", 50 < dist < 250)
    ws.set("target_too_close", dist < 60)
    ws.set("target_too_far", dist > 250)

    ws.set("has_line_of_sight", True)

    if dist > 0:
        dot = (dx * npc.facing_dx + dz * npc.facing_dz) / dist
        ws.set("facing_target", dot > 0.5)
    else:
        ws.set("facing_target", True)

    ws.set("can_sword", npc.can_sword())
    ws.set("can_bow", npc.can_bow())
    ws.set("can_dash", npc.can_dash())

    nearest_potion_dist = float("inf")
    for pickup in pickups:
        if pickup.alive and pickup.pickup_type == "potion":
            pdist = math.hypot(pickup.x - npc.x, pickup.z - npc.z)
            nearest_potion_dist = min(nearest_potion_dist, pdist)
    ws.set("potion_nearby", nearest_potion_dist < 150)
    ws.set("potion_reachable", nearest_potion_dist < 300)

    ws.set("target_damaged", False)
    ws.set("safe_distance", dist > 120)
    ws.set("at_vantage_point", False)
    ws.set("healed", False)

    return ws
