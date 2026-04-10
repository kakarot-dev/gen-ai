from __future__ import annotations

from dataclasses import dataclass, field
from ai.goap.world_state import WorldState

@dataclass
class GOAPGoal:
    name: str
    desired_state: dict[str, bool | float] = field(default_factory=dict)
    base_priority: float = 1.0

    def get_priority(self, world_state: WorldState) -> float:
        return self.base_priority

    def is_satisfied(self, world_state: WorldState) -> bool:
        return world_state.matches(self.desired_state)

class KillTargetGoal(GOAPGoal):
    
    def __init__(self):
        super().__init__(
            name="kill_target",
            desired_state={"target_damaged": True},
            base_priority=5.0,
        )

    def get_priority(self, ws: WorldState) -> float:
        if not ws.get("target_alive"):
            return 0
        p = self.base_priority
        health_pct = ws.get("health", 100) / 100
        if health_pct > 0.6:
            p += 3.0
        elif health_pct > 0.3:
            p += 1.0
        else:
            p -= 2.0
        return p

class SurviveGoal(GOAPGoal):
    
    def __init__(self):
        super().__init__(
            name="survive",
            desired_state={"safe_distance": True},
            base_priority=2.0,
        )

    def get_priority(self, ws: WorldState) -> float:
        health_pct = ws.get("health", 100) / 100
        p = self.base_priority
        if health_pct < 0.25:
            p += 10.0
        elif health_pct < 0.5:
            p += 6.0
        if ws.get("target_too_close") and health_pct < 0.5:
            p += 3.0    # enemy is close AND we're hurt
        return p

class HealGoal(GOAPGoal):
    
    def __init__(self):
        super().__init__(
            name="heal",
            desired_state={"healed": True},
            base_priority=1.0,
        )

    def get_priority(self, ws: WorldState) -> float:
        health_pct = ws.get("health", 100) / 100
        if health_pct > 0.6:
            return 0   # don't heal if healthy
        p = self.base_priority
        if ws.get("potion_reachable"):
            p += 5.0
        if health_pct < 0.25:
            p += 4.0
        return p

class ControlSpaceGoal(GOAPGoal):
    
    def __init__(self):
        super().__init__(
            name="control_space",
            desired_state={"in_bow_range": True, "safe_distance": True},
            base_priority=4.0,
        )

    def get_priority(self, ws: WorldState) -> float:
        p = self.base_priority
        if ws.get("target_too_close"):
            p += 5.0
        if not ws.get("in_bow_range"):
            p += 2.0
        health_pct = ws.get("health", 100) / 100
        if health_pct < 0.4:
            p += 3.0
        return p

def get_goals_for_type(char_type: str) -> list[GOAPGoal]:
    if char_type == "zombie":
        return [KillTargetGoal(), SurviveGoal(), HealGoal()]
    elif char_type == "skeleton":
        return [KillTargetGoal(), SurviveGoal(), HealGoal(), ControlSpaceGoal()]
    else:
        return [KillTargetGoal(), SurviveGoal()]
