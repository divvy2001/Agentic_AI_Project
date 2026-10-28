import random
from typing import List, Tuple, Optional

class Food:
    def __init__(self, snake_positions: List[Tuple[int,int]]):
        self.position: Optional[Tuple[int,int]] = None
        self.spawn(snake_positions)

    def spawn(self, snake_positions: List[Tuple[int,int]]) -> None:
        """Place food at a random position not occupied by the snake."""
        from game.constants import GRID_SIZE
        all_cells = [(x, y) for x in range(GRID_SIZE) for y in range(GRID_SIZE)]
        empty = [c for c in all_cells if c not in snake_positions]
        if not empty:
            self.position = None
            return
        self.position = random.choice(empty)

    def get_position(self) -> Optional[Tuple[int,int]]:
        return self.position
