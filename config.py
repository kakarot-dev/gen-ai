"""Global configuration for the game."""

# --- Display ---
TILE_SIZE = 32

# Tile types
TILE_EMPTY = 0
TILE_STONE = 1
TILE_WOOD = 2
TILE_LAVA = 3

# --- Characters ---
PLAYER_SPEED = 3.0
NPC_SPEED = 2.5
MAX_HEALTH = 100
MAX_STAMINA = 100
STAMINA_REGEN = 0.3

# --- Combat ---
SWORD_DAMAGE = 15
SWORD_RANGE = 40
SWORD_COOLDOWN = 30       # frames
BOW_DAMAGE = 10
BOW_COOLDOWN = 60         # frames
BOW_PROJECTILE_SPEED = 6.0
SHIELD_STAMINA_COST = 0.5  # per frame while blocking
SHIELD_DAMAGE_REDUCTION = 0.7

# --- Pickups ---
POTION_HEAL = 30
POTION_RESPAWN_TIME = 300  # frames

# --- Lava ---
LAVA_DAMAGE = 2  # per frame while standing on lava
LAVA_TICK_RATE = 15  # damage every N frames

# --- Jump / Gravity ---
GRAVITY = 0.4
JUMP_FORCE = 7.0
JUMP_STAMINA_COST = 10
GROUND_Y = 0.0

# --- Dash ---
DASH_SPEED = 8.0
DASH_DURATION = 8   # frames
DASH_COOLDOWN = 90   # frames
DASH_STAMINA_COST = 25
