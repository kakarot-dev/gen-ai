from enum import IntEnum

class MoveDirection(IntEnum):
    NONE = 0
    UP = 1
    DOWN = 2
    LEFT = 3
    RIGHT = 4
    UP_LEFT = 5
    UP_RIGHT = 6
    DOWN_LEFT = 7
    DOWN_RIGHT = 8

DIRECTION_VECTORS = {
    MoveDirection.NONE: (0, 0),
    MoveDirection.UP: (0, -1),
    MoveDirection.DOWN: (0, 1),
    MoveDirection.LEFT: (-1, 0),
    MoveDirection.RIGHT: (1, 0),
    MoveDirection.UP_LEFT: (-0.707, -0.707),
    MoveDirection.UP_RIGHT: (0.707, -0.707),
    MoveDirection.DOWN_LEFT: (-0.707, 0.707),
    MoveDirection.DOWN_RIGHT: (0.707, 0.707),
}

class ActionType(IntEnum):
    NOOP = 0
    MOVE = 1
    SWORD_ATTACK = 2
    BOW_ATTACK = 3
    DASH = 4
    SHIELD = 5
    JUMP = 6

class GameAction:
    

    __slots__ = ("action_type", "direction", "jump")

    def __init__(self, action_type: ActionType = ActionType.NOOP,
                 direction: MoveDirection = MoveDirection.NONE,
                 jump: bool = False):
        self.action_type = action_type
        self.direction = direction
        self.jump = jump

    def __repr__(self):
        return f"GameAction({self.action_type.name}, {self.direction.name})"
