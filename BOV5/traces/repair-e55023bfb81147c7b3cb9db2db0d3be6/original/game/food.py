import random
from typing import List, Tuple, Optional

class Food:
    """Food owns its position and spawning logic on a 20x20 grid."""

    def __init__(self, grid_size: int = 20):
        self.grid_size = grid_size
        self.position: Optional[Tuple[int, int]] = None

    def spawn(self, exclude: List[Tuple[int, int]]) -> None:
        """Place food at a random grid coordinate not in exclude.

        If no free cell exists, position becomes None.
        """
        all_cells = [(x, y) for y in range(self.grid_size) for x in range(self.grid_size)]
        free = [pos for pos in all_cells if pos not in exclude]
        if not free:
            self.position = None
            return
        self.position = random.choice(free)

    def get_position(self) -> Optional[Tuple[int, int]]:
        return self.position
