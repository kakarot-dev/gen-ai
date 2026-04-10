from __future__ import annotations

import math

import config as cfg
from simulation.actions import ActionType, MoveDirection, DIRECTION_VECTORS, GameAction

class Character:
    

    def __init__(self, x: float, z: float, char_type: str = "player"):
        self.x = x
        self.z = z
        self.vx = 0.0
        self.vz = 0.0
        self.facing_dx = 0.0
        self.facing_dz = 1.0

        self.y = cfg.GROUND_Y
        self.vy = 0.0
        self.on_ground = True

        self.char_type = char_type  # "player", "zombie", "skeleton"

        self.health = cfg.MAX_HEALTH
        self.stamina = cfg.MAX_STAMINA
        self.alive = True
        self.speed = cfg.PLAYER_SPEED if char_type == "player" else cfg.NPC_SPEED

        self.sword_cooldown = 0
        self.bow_cooldown = 0
        self.dash_cooldown = 0
        self.dash_timer = 0

        self.shielding = False

        self.damage_dealt = 0
        self.damage_taken = 0
        self.kills = 0
        self.deaths = 0

        self.hit_flash = 0

    @property
    def radius(self) -> float:
        return cfg.TILE_SIZE * 0.4

    def take_damage(self, amount: float, attacker: Character | None = None):
        if not self.alive:
            return 0
        if self.shielding:
            amount *= (1 - cfg.SHIELD_DAMAGE_REDUCTION)
        actual = min(amount, self.health)
        self.health -= actual
        self.damage_taken += actual
        self.hit_flash = 8
        if attacker:
            attacker.damage_dealt += actual
        if self.health <= 0:
            self.health = 0
            self.alive = False
            self.deaths += 1
            if attacker:
                attacker.kills += 1
        return actual

    def heal(self, amount: float):
        if not self.alive:
            return
        self.health = min(self.health + amount, cfg.MAX_HEALTH)

    def can_sword(self) -> bool:
        return self.alive and self.sword_cooldown <= 0 and self.dash_timer <= 0

    def can_bow(self) -> bool:
        return self.alive and self.bow_cooldown <= 0 and self.dash_timer <= 0

    def can_dash(self) -> bool:
        return (self.alive and self.dash_cooldown <= 0
                and self.dash_timer <= 0
                and self.stamina >= cfg.DASH_STAMINA_COST)

    def can_jump(self) -> bool:
        return (self.alive and self.on_ground
                and self.stamina >= cfg.JUMP_STAMINA_COST)

    def apply_action(self, action: GameAction) -> Projectile | None:
        
        if not self.alive:
            return None

        projectile = None
        self.shielding = False

        dx, dz = DIRECTION_VECTORS[action.direction]
        if dx != 0 or dz != 0:
            self.facing_dx = dx
            self.facing_dz = dz

        if action.jump and self.can_jump():
            self.vy = cfg.JUMP_FORCE
            self.on_ground = False
            self.stamina -= cfg.JUMP_STAMINA_COST

        if action.action_type == ActionType.MOVE:
            if self.dash_timer > 0:
                self.vx = self.facing_dx * cfg.DASH_SPEED
                self.vz = self.facing_dz * cfg.DASH_SPEED
            else:
                self.vx = dx * self.speed
                self.vz = dz * self.speed

        elif action.action_type == ActionType.SWORD_ATTACK:
            if self.dash_timer <= 0:
                self.vx = dx * self.speed
                self.vz = dz * self.speed
            if self.can_sword():
                self.sword_cooldown = cfg.SWORD_COOLDOWN

        elif action.action_type == ActionType.BOW_ATTACK:
            if self.dash_timer <= 0:
                self.vx = dx * self.speed * 0.5
                self.vz = dz * self.speed * 0.5
            if self.can_bow():
                self.bow_cooldown = cfg.BOW_COOLDOWN
                projectile = Projectile(
                    self.x + self.facing_dx * self.radius,
                    self.y + 10,
                    self.z + self.facing_dz * self.radius,
                    self.facing_dx * cfg.BOW_PROJECTILE_SPEED,
                    0,
                    self.facing_dz * cfg.BOW_PROJECTILE_SPEED,
                    damage=cfg.BOW_DAMAGE,
                    owner=self,
                )

        elif action.action_type == ActionType.DASH:
            if self.can_dash():
                self.dash_timer = cfg.DASH_DURATION
                self.dash_cooldown = cfg.DASH_COOLDOWN
                self.stamina -= cfg.DASH_STAMINA_COST
                dash_dx = dx if dx != 0 else self.facing_dx
                dash_dz = dz if dz != 0 else self.facing_dz
                self.facing_dx = dash_dx
                self.facing_dz = dash_dz
                self.vx = dash_dx * cfg.DASH_SPEED
                self.vz = dash_dz * cfg.DASH_SPEED
            else:
                self.vx = dx * self.speed
                self.vz = dz * self.speed

        elif action.action_type == ActionType.SHIELD:
            self.shielding = True
            self.vx = dx * self.speed * 0.3
            self.vz = dz * self.speed * 0.3
            self.stamina = max(0, self.stamina - cfg.SHIELD_STAMINA_COST)
            if self.stamina <= 0:
                self.shielding = False

        elif action.action_type == ActionType.NOOP:
            self.vx = 0
            self.vz = 0

        return projectile

    def tick_physics(self):
        
        if not self.on_ground:
            self.vy -= cfg.GRAVITY
            self.y += self.vy
            if self.y <= cfg.GROUND_Y:
                self.y = cfg.GROUND_Y
                self.vy = 0
                self.on_ground = True

    def tick_cooldowns(self):
        
        if self.sword_cooldown > 0:
            self.sword_cooldown -= 1
        if self.bow_cooldown > 0:
            self.bow_cooldown -= 1
        if self.dash_cooldown > 0:
            self.dash_cooldown -= 1
        if self.dash_timer > 0:
            self.dash_timer -= 1
        if self.hit_flash > 0:
            self.hit_flash -= 1
        if not self.shielding and self.stamina < cfg.MAX_STAMINA:
            self.stamina = min(cfg.MAX_STAMINA, self.stamina + cfg.STAMINA_REGEN)

    def reset(self, x: float, z: float):
        self.x = x
        self.z = z
        self.vx = 0
        self.vz = 0
        self.y = cfg.GROUND_Y
        self.vy = 0
        self.on_ground = True
        self.health = cfg.MAX_HEALTH
        self.stamina = cfg.MAX_STAMINA
        self.alive = True
        self.sword_cooldown = 0
        self.bow_cooldown = 0
        self.dash_cooldown = 0
        self.dash_timer = 0
        self.shielding = False
        self.hit_flash = 0

    def distance_to(self, other: Character) -> float:
        
        return math.hypot(self.x - other.x, self.z - other.z)

class Projectile:
    

    def __init__(self, x: float, y: float, z: float,
                 vx: float, vy: float, vz: float,
                 damage: float, owner: Character):
        self.x = x
        self.y = y
        self.z = z
        self.vx = vx
        self.vy = vy
        self.vz = vz
        self.damage = damage
        self.owner = owner
        self.alive = True
        self.lifetime = 120

    @property
    def radius(self) -> float:
        return 4

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.z += self.vz
        self.vy -= cfg.GRAVITY * 0.3
        self.lifetime -= 1
        if self.lifetime <= 0 or self.y < -10:
            self.alive = False

class Pickup:
    

    def __init__(self, x: float, z: float, pickup_type: str = "potion"):
        self.x = x
        self.z = z
        self.y = cfg.GROUND_Y
        self.pickup_type = pickup_type
        self.alive = True
        self.respawn_timer = 0

    @property
    def radius(self) -> float:
        return cfg.TILE_SIZE * 0.3

    def collect(self, character: Character):
        if not self.alive:
            return
        if self.pickup_type == "potion":
            character.heal(cfg.POTION_HEAL)
        self.alive = False
        self.respawn_timer = cfg.POTION_RESPAWN_TIME

    def update(self):
        if not self.alive:
            self.respawn_timer -= 1
            if self.respawn_timer <= 0:
                self.alive = True
