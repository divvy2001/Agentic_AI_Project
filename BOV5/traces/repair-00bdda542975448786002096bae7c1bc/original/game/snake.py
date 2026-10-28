from typing import List, Tuple, Set

class Snake:
    """Manages snake body, movement, growth, and self-collision."""
    def __init__(self, initial_body: List[Tuple[int,int]], direction: Tuple[int,int]):
        # body is a list of (x,y) with head at index 0
        self.body: List[Tuple[int,int]] = list(initial_body)
        self.dx, self.dy = direction

    def head(self) -> Tuple[int,int]:
        return self.body[0]

    def occupies(self) -> Set[Tuple[int,int]]:
        return set(self.body)

    def set_direction(self, dx: int, dy: int) -> None:
        # prevent reversing into itself
        if (dx, dy) == (-self.dx, -self.dy):
            return
        self.dx, self.dy = dx, dy

    def next_head(self) -> Tuple[int,int]:
        hx, hy = self.head()
        return (hx + self.dx, hy + self.dy)

    def check_self_collision(self, next_head: Tuple[int,int], grow: bool=False) -> bool:
        # If growing, the tail won't move, so colliding with any part is fatal.
        # If not growing, moving into the current tail cell is allowed (it will vacate).
        if grow:
            return next_head in self.body
        else:
            # allowed to move into tail position
            tail = self.body[-1]
            if next_head == tail:
                return False
            return next_head in self.body

    def move(self, grow: bool=False) -> Tuple[int,int]:
        nh = self.next_head()
        self.body.insert(0, nh)
        if not grow:
            self.body.pop()
        return nh

    def reset(self, initial_body: List[Tuple[int,int]], direction: Tuple[int,int]):
        self.body = list(initial_body)
        self.dx, self.dy = direction
