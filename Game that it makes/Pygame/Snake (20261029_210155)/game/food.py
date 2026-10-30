from typing import Set, Tuple
import random

class Food:
    """Manages food position on the GRID.

    Methods:
    - spawn(exclude: Set[Tuple[int,int]]) -> None
    - get_pos() -> Tuple[int,int]
    """

    def __init__(self, grid_w: int, grid_h: int) -> None:
        self.grid_w = grid_w
        self.grid_h = grid_h
        self.pos = (0, 0)

    def spawn(self, exclude: Set[Tuple[int, int]]) -> None:
        """Choose a random position not in exclude. If no positions available, keep current pos."""
        all_positions = [
            (x, y) for x in range(self.grid_w) for y in range(self.grid_h) if (x, y) not in exclude
        ]
        if not all_positions:
            # No free space; leave position unchanged
            return
        self.pos = random.choice(all_positions)

    def get_pos(self) -> Tuple[int, int]:
        return self.pos
