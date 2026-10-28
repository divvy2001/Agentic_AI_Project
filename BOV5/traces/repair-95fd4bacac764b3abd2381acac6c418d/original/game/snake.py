import random
from typing import List, Tuple

class Snake:
    """Snake model: positions is a list of (x,y) tuples. Head is positions[-1]."""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        # Start in middle of GRID_SIZE, length 3, moving right
        from game.constants import GRID_SIZE
        mid = GRID_SIZE // 2
        # positions left-to-right, head at last
        self.positions: List[Tuple[int,int]] = [
            (mid - 1, mid),
            (mid, mid),
            (mid + 1, mid),
        ]
        # initial direction: right
        self.direction = (1, 0)

    def get_positions(self) -> List[Tuple[int,int]]:
        return list(self.positions)

    def head(self) -> Tuple[int,int]:
        return self.positions[-1]

    def set_direction(self, dx: int, dy: int) -> None:
        # Prevent reversing directly into itself
        cur_dx, cur_dy = self.direction
        if (dx, dy) == (-cur_dx, -cur_dy):
            return
        self.direction = (dx, dy)

    def move(self, grow: bool = False) -> Tuple[int,int]:
        """Move snake by one cell in current direction. If grow, keep the tail.
        Returns the new head position."""
        head_x, head_y = self.head()
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)
        self.positions.append(new_head)
        if not grow:
            # remove tail
            self.positions.pop(0)
        return new_head

    def collides_with_self(self) -> bool:
        # head collides with any other part
        head = self.head()
        return head in self.positions[:-1]
