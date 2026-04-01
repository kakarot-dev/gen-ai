"""GOAP action definitions — preconditions and effects."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GOAPAction:
    """A high-level action the NPC can plan to take.

    The GOAP planner chains these together using A* to satisfy goals.
    Each action has:
        - preconditions: world state facts that must be true to use this action
        - effects: world state changes when this action completes
        - cost: used by A* to prefer cheaper plans
        - name: identifier passed to RL policy as the current goal
    """
    name: str
    preconditions: dict[str, bool | float] = field(default_factory=dict)
    effects: dict[str, bool | float] = field(default_factory=dict)
    cost: float = 1.0

    def is_usable(self, world_state) -> bool:
        return world_state.matches(self.preconditions)


# ============================================================
# ZOMBIE (melee) actions
# ============================================================

ZOMBIE_ACTIONS = [
    GOAPAction(
        name="chase_target",
        preconditions={"alive": True, "target_alive": True},
        effects={"in_melee_range": True, "target_too_far": False},
        cost=2.0,
    ),
    GOAPAction(
        name="melee_attack",
        preconditions={"alive": True, "target_alive": True, "in_melee_range": True,
                       "can_sword": True},
        effects={"target_damaged": True},
        cost=1.0,
    ),
    GOAPAction(
        name="flank_target",
        preconditions={"alive": True, "target_alive": True},
        effects={"in_melee_range": True, "facing_target": True},
        cost=3.0,
    ),
    GOAPAction(
        name="dash_attack",
        preconditions={"alive": True, "target_alive": True, "can_dash": True,
                       "has_stamina": True},
        effects={"in_melee_range": True, "target_damaged": True},
        cost=2.5,
    ),
    GOAPAction(
        name="retreat",
        preconditions={"alive": True, "low_health": True},
        effects={"safe_distance": True},
        cost=1.5,
    ),
    GOAPAction(
        name="heal",
        preconditions={"alive": True, "low_health": True, "potion_reachable": True},
        effects={"low_health": False, "healed": True},
        cost=2.0,
    ),
]


# ============================================================
# SKELETON (ranged) actions
# ============================================================

SKELETON_ACTIONS = [
    GOAPAction(
        name="ranged_attack",
        preconditions={"alive": True, "target_alive": True, "in_bow_range": True,
                       "has_line_of_sight": True, "can_bow": True},
        effects={"target_damaged": True},
        cost=1.0,
    ),
    GOAPAction(
        name="find_vantage_point",
        preconditions={"alive": True, "target_alive": True},
        effects={"in_bow_range": True, "has_line_of_sight": True,
                 "at_vantage_point": True},
        cost=2.5,
    ),
    GOAPAction(
        name="maintain_distance",
        preconditions={"alive": True, "target_too_close": True},
        effects={"target_too_close": False, "safe_distance": True,
                 "in_bow_range": True},
        cost=1.5,
    ),
    GOAPAction(
        name="kite_target",
        preconditions={"alive": True, "target_alive": True, "can_bow": True},
        effects={"target_damaged": True, "safe_distance": True},
        cost=2.0,
    ),
    GOAPAction(
        name="retreat",
        preconditions={"alive": True, "low_health": True},
        effects={"safe_distance": True},
        cost=1.5,
    ),
    GOAPAction(
        name="heal",
        preconditions={"alive": True, "low_health": True, "potion_reachable": True},
        effects={"low_health": False, "healed": True},
        cost=2.0,
    ),
    GOAPAction(
        name="dash_away",
        preconditions={"alive": True, "target_too_close": True, "can_dash": True},
        effects={"target_too_close": False, "safe_distance": True},
        cost=1.0,
    ),
]


def get_actions_for_type(char_type: str) -> list[GOAPAction]:
    if char_type == "zombie":
        return ZOMBIE_ACTIONS
    elif char_type == "skeleton":
        return SKELETON_ACTIONS
    else:
        return ZOMBIE_ACTIONS  # fallback
