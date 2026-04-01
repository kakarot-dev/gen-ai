"""GOAP A* planner — finds action sequences to satisfy goals."""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from ai.goap.world_state import WorldState
from ai.goap.actions import GOAPAction
from ai.goap.goals import GOAPGoal


@dataclass(order=True)
class PlanNode:
    """A node in the A* search over action space."""
    cost: float
    state: WorldState = field(compare=False)
    actions: list[GOAPAction] = field(compare=False, default_factory=list)


class GOAPPlanner:
    """Plans a sequence of GOAP actions to satisfy the highest-priority goal."""

    def __init__(self, available_actions: list[GOAPAction],
                 goals: list[GOAPGoal], max_depth: int = 5):
        self.available_actions = available_actions
        self.goals = goals
        self.max_depth = max_depth
        self.current_plan: list[GOAPAction] = []
        self.current_goal: GOAPGoal | None = None
        self.plan_step: int = 0
        self._replan_cooldown: int = 0

    def get_current_action_name(self) -> str:
        """Return the name of the current action being executed."""
        if self.current_plan and self.plan_step < len(self.current_plan):
            return self.current_plan[self.plan_step].name
        return "idle"

    def update(self, world_state: WorldState, force_replan: bool = False) -> str:
        """Update the planner and return the current action name.

        Re-plans when:
        - No current plan
        - Current goal is satisfied
        - A higher-priority goal emerges
        - Plan step exceeded
        - Forced replan (world changed significantly)
        """
        self._replan_cooldown = max(0, self._replan_cooldown - 1)

        needs_replan = force_replan or self._replan_cooldown <= 0

        if not needs_replan and self.current_plan and self.plan_step < len(self.current_plan):
            # Still executing current plan
            return self.current_plan[self.plan_step].name

        # Find highest priority goal
        best_goal = self._select_goal(world_state)

        if best_goal is None:
            self.current_plan = []
            self.current_goal = None
            return "idle"

        # Check if we need to switch goals
        goal_changed = (best_goal is not self.current_goal)
        plan_exhausted = (not self.current_plan or
                          self.plan_step >= len(self.current_plan))

        if goal_changed or plan_exhausted or force_replan:
            # Run A* planner
            plan = self._plan(world_state, best_goal)
            if plan:
                self.current_plan = plan
                self.current_goal = best_goal
                self.plan_step = 0
                self._replan_cooldown = 30  # don't replan for 30 frames
            else:
                # No plan found — fallback
                self.current_plan = []
                self.current_goal = best_goal
                return "idle"

        if self.current_plan and self.plan_step < len(self.current_plan):
            return self.current_plan[self.plan_step].name
        return "idle"

    def advance_step(self):
        """Call when the current action is considered complete."""
        self.plan_step += 1

    def _select_goal(self, world_state: WorldState) -> GOAPGoal | None:
        """Pick the highest priority unsatisfied goal."""
        best = None
        best_priority = -1
        for goal in self.goals:
            if goal.is_satisfied(world_state):
                continue
            p = goal.get_priority(world_state)
            if p > best_priority:
                best_priority = p
                best = goal
        return best

    def _plan(self, start_state: WorldState, goal: GOAPGoal) -> list[GOAPAction] | None:
        """A* search to find an action sequence satisfying the goal."""
        open_set: list[PlanNode] = []
        heapq.heappush(open_set, PlanNode(cost=0, state=start_state, actions=[]))

        visited = set()
        iterations = 0
        max_iterations = 200

        while open_set and iterations < max_iterations:
            iterations += 1
            node = heapq.heappop(open_set)

            # Check if goal is satisfied
            if goal.is_satisfied(node.state):
                return node.actions

            # Max depth check
            if len(node.actions) >= self.max_depth:
                continue

            # Create a hashable state key (simplified)
            state_key = frozenset(
                (k, v) for k, v in node.state.facts.items()
                if isinstance(v, bool)
            )
            if state_key in visited:
                continue
            visited.add(state_key)

            # Try each available action
            for action in self.available_actions:
                if not action.is_usable(node.state):
                    continue

                new_state = node.state.apply(action.effects)
                new_cost = node.cost + action.cost
                new_actions = node.actions + [action]

                heapq.heappush(open_set, PlanNode(
                    cost=new_cost, state=new_state, actions=new_actions
                ))

        # No plan found — return the best partial plan if any
        return None
