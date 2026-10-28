import random
from typing import Tuple, Set

class Food:
    def __init__(self, grid_size: int):
        self.grid_size = grid_size
        self.position: Tuple[int,int] = (0, 0)

    def respawn(self, occupied: Set[Tuple[int,int]]) -> None:
        choices = [ (x,y) for x in range(self.grid_size) for y in range(self.grid_size) if (x,y) not in occupied ]
        if not choices:
            # No empty spot: keep current position
            return
        self.position = random.choice(choices)
