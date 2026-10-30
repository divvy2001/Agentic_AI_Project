from typing import List, Tuple

class Snake:
    """Snake model for grid-based movement.

    body: list of (x,y) tuples. Head is body[-1].
    dir: (dx,dy) current movement direction.
    grow: bool flag; when True, next move will increase length by 1.
    """

    def __init__(self, start_positions: List[Tuple[int, int]], start_dir: Tuple[int, int]) -> None:
        self.body = list(start_positions)
        self.dir = start_dir
        self.grow = False

    def head(self) -> Tuple[int, int]:
        return self.body[-1]

    def move(self) -> None:
        """Advance the snake by one cell in the current direction.
        If grow is True, extend without removing tail once.
        """
        hx, hy = self.head()
        dx, dy = self.dir
        new_head = (hx + dx, hy + dy)
        if self.grow:
            # keep tail, just append new head
            self.body.append(new_head)
            self.grow = False
        else:
            # move forward: drop tail, append head
            self.body.pop(0)
            self.body.append(new_head)

    def change_direction(self, new_dir: Tuple[int, int]) -> bool:
        """Change direction if new_dir is not the precise opposite of current.
        Returns True if direction changed, False otherwise.
        """
        ndx, ndy = new_dir
        cdx, cdy = self.dir
        # prevent reversing directly into itself
        if (ndx == -cdx and ndy == -cdy) or (ndx == cdx and ndy == cdy):
            return False
        self.dir = (ndx, ndy)
        return True

    def grow_by_one(self) -> None:
        self.grow = True

    def collides_with_self(self) -> bool:
        """Return True if head collides with any other body segment."""
        head = self.head()
        return head in self.body[:-1]

    def collides_with_wall(self, grid_w: int, grid_h: int) -> bool:
        hx, hy = self.head()
        return not (0 <= hx < grid_w and 0 <= hy < grid_h)
