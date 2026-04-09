"""Arena / tile map for the game world."""
from __future__ import annotations

import config as cfg


# Pre-built arena layout (20 rows x 30 cols)
# 0=empty, 1=stone wall, 2=wood, 3=lava
_DEFAULT_LAYOUT = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1],
    [1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1],
    [1, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]


class Arena:
    """Tile-based arena map."""

    def __init__(self, layout: list[list[int]] | None = None):
        self.tiles = layout if layout is not None else [row[:] for row in _DEFAULT_LAYOUT]
        self.rows = len(self.tiles)
        self.cols = len(self.tiles[0])
        self.width = self.cols * cfg.TILE_SIZE
        self.height = self.rows * cfg.TILE_SIZE

    def get_tile(self, col: int, row: int) -> int:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.tiles[row][col]
        return cfg.TILE_STONE  # out of bounds = wall

    def is_walkable(self, col: int, row: int) -> bool:
        tile = self.get_tile(col, row)
        return tile in (cfg.TILE_EMPTY, cfg.TILE_LAVA)

    def is_lava(self, col: int, row: int) -> bool:
        return self.get_tile(col, row) == cfg.TILE_LAVA

    def blocks_sight(self, col: int, row: int) -> bool:
        """Does this tile block line of sight?"""
        tile = self.get_tile(col, row)
        return tile in (cfg.TILE_STONE, cfg.TILE_WOOD)

    def has_line_of_sight(self, x1: float, y1: float, x2: float, y2: float) -> bool:
        """Raycast between two points — True if no wall blocks."""
        import math
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist < 1:
            return True
        steps = max(int(dist / (cfg.TILE_SIZE * 0.5)), 2)
        for i in range(1, steps):
            t = i / steps
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            col, row = self.pixel_to_tile(x, y)
            if self.blocks_sight(col, row):
                return False
        return True

    def nearest_cover(self, x: float, y: float, from_x: float, from_y: float,
                      max_search_radius: int = 8):
        """Find closest wall tile that blocks LoS from (from_x, from_y).

        Returns (tile_col, tile_row) or None.
        """
        import math
        cx, cy = self.pixel_to_tile(x, y)
        best = None
        best_dist = float('inf')
        for dr in range(-max_search_radius, max_search_radius + 1):
            for dc in range(-max_search_radius, max_search_radius + 1):
                col, row = cx + dc, cy + dr
                if not (0 <= row < self.rows and 0 <= col < self.cols):
                    continue
                if not self.blocks_sight(col, row):
                    continue
                # Position behind the wall (opposite side from attacker)
                wx = col * cfg.TILE_SIZE + cfg.TILE_SIZE / 2
                wy = row * cfg.TILE_SIZE + cfg.TILE_SIZE / 2
                # Place agent on opposite side of wall from attacker
                ax = from_x - wx
                ay = from_y - wy
                norm = math.hypot(ax, ay) + 1e-6
                behind_x = wx - (ax / norm) * cfg.TILE_SIZE
                behind_y = wy - (ay / norm) * cfg.TILE_SIZE
                d = math.hypot(behind_x - x, behind_y - y)
                if d < best_dist:
                    # Validate walkability
                    if self.is_position_walkable(behind_x, behind_y, cfg.TILE_SIZE * 0.4):
                        best = (behind_x, behind_y)
                        best_dist = d
        return best

    def pixel_to_tile(self, x: float, y: float) -> tuple[int, int]:
        return int(x // cfg.TILE_SIZE), int(y // cfg.TILE_SIZE)

    def tile_to_pixel_center(self, col: int, row: int) -> tuple[float, float]:
        return col * cfg.TILE_SIZE + cfg.TILE_SIZE / 2, row * cfg.TILE_SIZE + cfg.TILE_SIZE / 2

    def is_position_walkable(self, x: float, y: float, radius: float) -> bool:
        """Check if a circle at (x, y) with given radius fits without hitting walls."""
        # Check all tiles the circle could overlap
        min_col = int((x - radius) // cfg.TILE_SIZE)
        max_col = int((x + radius) // cfg.TILE_SIZE)
        min_row = int((y - radius) // cfg.TILE_SIZE)
        max_row = int((y + radius) // cfg.TILE_SIZE)

        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                if not self.is_walkable(col, row):
                    # AABB collision with tile
                    tile_left = col * cfg.TILE_SIZE
                    tile_top = row * cfg.TILE_SIZE
                    tile_right = tile_left + cfg.TILE_SIZE
                    tile_bottom = tile_top + cfg.TILE_SIZE

                    # Find closest point on tile to circle center
                    closest_x = max(tile_left, min(x, tile_right))
                    closest_y = max(tile_top, min(y, tile_bottom))

                    dist_sq = (x - closest_x) ** 2 + (y - closest_y) ** 2
                    if dist_sq < radius ** 2:
                        return False
        return True

    def get_spawn_positions(self) -> list[tuple[float, float]]:
        """Return good spawn positions (open areas near corners)."""
        # Specific open tiles verified against the default layout
        spawn_tiles = [
            (2, 2),   # top-left
            (27, 2),  # top-right
            (2, 17),  # bottom-left
            (27, 17), # bottom-right
        ]
        positions = []
        for col, row in spawn_tiles:
            if self.is_walkable(col, row):
                positions.append(self.tile_to_pixel_center(col, row))
        # Fallback: scan for open tiles if none found
        if not positions:
            for row in range(1, self.rows - 1):
                for col in range(1, self.cols - 1):
                    if self.is_walkable(col, row):
                        positions.append(self.tile_to_pixel_center(col, row))
                        if len(positions) >= 4:
                            return positions
        return positions

    def get_pickup_positions(self) -> list[tuple[float, float]]:
        """Return positions for item pickups."""
        positions = []
        # Place potions in symmetrical positions
        spots = [
            (7, 5), (22, 5),
            (7, 14), (22, 14),
            (14, 3), (14, 16),
        ]
        for col, row in spots:
            if self.is_walkable(col, row):
                positions.append(self.tile_to_pixel_center(col, row))
        return positions
