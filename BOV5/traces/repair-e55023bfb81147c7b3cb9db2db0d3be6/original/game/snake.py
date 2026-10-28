from typing import List, Tuple

class Snake:
    """Snake owns its positions on the grid and movement logic.

    Grid coordinates are (x, y) with (0,0) at top-left.
    """

    OPPOSITE = {
        'UP': 'DOWN',
        'DOWN': 'UP',
        'LEFT': 'RIGHT',
        'RIGHT': 'LEFT',
    }

    DIR_VECTORS = {
        'UP': (0, -1),
        'DOWN': (0, 1),
        'LEFT': (-1, 0),
        'RIGHT': (1, 0),
    }

    def __init__(self):
        self.positions: List[Tuple[int, int]] = []
        self.direction: str = 'RIGHT'
        self.pending_direction: str = 'RIGHT'
        self.grow_pending: int = 0

    def reset(self, start_positions: List[Tuple[int, int]], direction: str) -> None:
        """Reset snake to given positions and direction."""
        self.positions = list(start_positions)
        self.direction = direction
        self.pending_direction = direction
        self.grow_pending = 0

    def get_positions(self) -> List[Tuple[int, int]]:
        return list(self.positions)

    def get_head(self) -> Tuple[int, int]:
        return tuple(self.positions[0])

    def change_direction(self, direction: str) -> None:
        """Schedule a direction change if it is not a direct reverse."""
        if direction not in self.DIR_VECTORS:
            return
        # Prevent reversing into itself: ignore if opposite of current
        if self.OPPOSITE.get(direction) == self.direction:
            return
        # Accept change for next move
        self.pending_direction = direction

    def grow(self, amount: int = 1) -> None:
        self.grow_pending += max(0, int(amount))

    def update(self, grow: bool = False) -> None:
        """Advance the snake by one grid cell according to current direction.

        If grow is True, the tail is not removed this move (immediate growth).
        Otherwise tail is removed unless there is grow_pending queued.
        Caller must check collisions (walls/self) after calling update.
        """
        # Apply pending direction at time of movement
        self.direction = self.pending_direction
        dx, dy = self.DIR_VECTORS[self.direction]
        head_x, head_y = self.positions[0]
        new_head = (head_x + dx, head_y + dy)
        # Insert new head
        self.positions.insert(0, new_head)
        # Remove tail unless growing now or growth queued
        if grow:
            # immediate growth for this move
            return
        if self.grow_pending > 0:
            self.grow_pending -= 1
            return
        # Normal move: remove last
        self.positions.pop()

    def is_collision_with_self(self) -> bool:
        head = self.get_head()
        # If head overlaps any other segment
        return head in self.positions[1:]
