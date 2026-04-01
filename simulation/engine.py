"""Core game engine — pure game state logic, no rendering."""
from __future__ import annotations

import math

import config as cfg
from simulation.arena import Arena
from simulation.entities import Character, Projectile, Pickup
from simulation.actions import GameAction, ActionType


class GameEngine:
    """Manages game state and processes one tick at a time.

    Coordinates: x,z = horizontal plane, y = vertical (jump).
    """

    def __init__(self, num_npcs: int = 1):
        self.arena = Arena()
        self.frame = 0

        spawns = self.arena.get_spawn_positions()
        self.player = Character(spawns[0][0], spawns[0][1], char_type="player")

        self.npcs: list[Character] = []
        npc_types = ["zombie", "skeleton"]
        for i in range(min(num_npcs, len(spawns) - 1)):
            npc_type = npc_types[i % len(npc_types)]
            npc = Character(spawns[i + 1][0], spawns[i + 1][1], char_type=npc_type)
            self.npcs.append(npc)

        self.all_characters: list[Character] = [self.player] + self.npcs

        self.projectiles: list[Projectile] = []

        self.pickups: list[Pickup] = []
        for pos in self.arena.get_pickup_positions():
            self.pickups.append(Pickup(pos[0], pos[1], pickup_type="potion"))

        self.done = False
        self.winner: Character | None = None

    def reset(self):
        self.frame = 0
        self.done = False
        self.winner = None
        self.projectiles.clear()

        spawns = self.arena.get_spawn_positions()
        self.player.reset(spawns[0][0], spawns[0][1])
        for i, npc in enumerate(self.npcs):
            npc.reset(spawns[i + 1][0], spawns[i + 1][1])

        for pickup in self.pickups:
            pickup.alive = True
            pickup.respawn_timer = 0

    def step(self, actions: dict[Character, GameAction]):
        if self.done:
            return

        self.frame += 1

        # 1. Apply actions and collect new projectiles
        for char, action in actions.items():
            proj = char.apply_action(action)
            if proj is not None:
                self.projectiles.append(proj)

        # 2. Move characters (horizontal) and resolve wall collisions
        for char in self.all_characters:
            if not char.alive:
                continue
            self._move_character(char)

        # 3. Jump / gravity physics
        for char in self.all_characters:
            if char.alive:
                char.tick_physics()

        # 4. Process sword attacks (melee hit detection)
        for char, action in actions.items():
            if action.action_type == ActionType.SWORD_ATTACK and char.sword_cooldown == cfg.SWORD_COOLDOWN:
                self._process_sword_hit(char)

        # 5. Update projectiles
        for proj in self.projectiles:
            if not proj.alive:
                continue
            proj.update()
            self._check_projectile_collisions(proj)
        self.projectiles = [p for p in self.projectiles if p.alive]

        # 6. Lava damage
        for char in self.all_characters:
            if not char.alive:
                continue
            col, row = self.arena.pixel_to_tile(char.x, char.z)
            if self.arena.is_lava(col, row) and self.frame % cfg.LAVA_TICK_RATE == 0:
                char.take_damage(cfg.LAVA_DAMAGE)

        # 7. Pickup collection
        for char in self.all_characters:
            if not char.alive:
                continue
            for pickup in self.pickups:
                if not pickup.alive:
                    continue
                dist = math.hypot(char.x - pickup.x, char.z - pickup.z)
                if dist < char.radius + pickup.radius:
                    pickup.collect(char)

        # 8. Update pickups (respawn timers)
        for pickup in self.pickups:
            pickup.update()

        # 9. Tick cooldowns
        for char in self.all_characters:
            char.tick_cooldowns()

        # 10. Check win condition
        self._check_win_condition()

    def _move_character(self, char: Character):
        new_x = char.x + char.vx
        new_z = char.z + char.vz

        if self.arena.is_position_walkable(new_x, new_z, char.radius):
            char.x = new_x
            char.z = new_z
            return

        if self.arena.is_position_walkable(new_x, char.z, char.radius):
            char.x = new_x
            return

        if self.arena.is_position_walkable(char.x, new_z, char.radius):
            char.z = new_z

    def _process_sword_hit(self, attacker: Character):
        for target in self.all_characters:
            if target is attacker or not target.alive:
                continue

            dx = target.x - attacker.x
            dz = target.z - attacker.z
            dist = math.hypot(dx, dz)

            if dist > cfg.SWORD_RANGE + target.radius:
                continue

            # Check vertical proximity (can't sword someone far above/below)
            dy = abs(target.y - attacker.y)
            if dy > 20:
                continue

            if dist > 0:
                dot = (dx * attacker.facing_dx + dz * attacker.facing_dz) / dist
                if dot > 0.2:
                    target.take_damage(cfg.SWORD_DAMAGE, attacker)

    def _check_projectile_collisions(self, proj: Projectile):
        col, row = self.arena.pixel_to_tile(proj.x, proj.z)
        if not self.arena.is_walkable(col, row):
            proj.alive = False
            return

        for char in self.all_characters:
            if char is proj.owner or not char.alive:
                continue
            hdist = math.hypot(proj.x - char.x, proj.z - char.z)
            vdist = abs(proj.y - char.y)
            if hdist < proj.radius + char.radius and vdist < 20:
                char.take_damage(proj.damage, proj.owner)
                proj.alive = False
                return

    def _check_win_condition(self):
        alive_chars = [c for c in self.all_characters if c.alive]
        if len(alive_chars) <= 1:
            self.done = True
            self.winner = alive_chars[0] if alive_chars else None

    def get_state_snapshot(self) -> dict:
        """Return a snapshot of the current game state."""
        return {
            "frame": self.frame,
            "done": self.done,
            "winner": self.winner.char_type if self.winner else None,
            "arena": {
                "rows": self.arena.rows,
                "cols": self.arena.cols,
                "tiles": self.arena.tiles,
            },
            "characters": [
                {
                    "type": c.char_type,
                    "x": round(c.x, 1),
                    "y": round(c.y, 1),
                    "z": round(c.z, 1),
                    "health": round(c.health, 1),
                    "max_health": cfg.MAX_HEALTH,
                    "stamina": round(c.stamina, 1),
                    "max_stamina": cfg.MAX_STAMINA,
                    "alive": c.alive,
                    "facing_dx": round(c.facing_dx, 2),
                    "facing_dz": round(c.facing_dz, 2),
                    "shielding": c.shielding,
                    "on_ground": c.on_ground,
                    "sword_cd": c.sword_cooldown,
                    "bow_cd": c.bow_cooldown,
                    "dash_timer": c.dash_timer,
                    "hit_flash": c.hit_flash,
                }
                for c in self.all_characters
            ],
            "projectiles": [
                {"x": round(p.x, 1), "y": round(p.y, 1), "z": round(p.z, 1),
                 "vx": round(p.vx, 2), "vy": round(p.vy, 2), "vz": round(p.vz, 2)}
                for p in self.projectiles if p.alive
            ],
            "pickups": [
                {"x": round(p.x, 1), "z": round(p.z, 1), "alive": p.alive,
                 "type": p.pickup_type}
                for p in self.pickups
            ],
        }
