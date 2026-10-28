import random
from typing import List, Tuple

class Maze:
    """Tile-based maze. grid[x][y] is True for open, False for wall.
    Coordinates: x in [0..width-1], y in [0..height-1], origin top-left.
    """
    def __init__(self, width: int = 15, height: int = 15):
        self.width = width
        self.height = height
        self.grid: List[List[bool]] = []
        self.reset()

    def reset(self) -> None:
        # Generate a simple maze using recursive backtracker on an odd-size grid
        w = self.width
        h = self.height
        # Initialize all as walls
        self.grid = [[False for _ in range(h)] for _ in range(w)]

        # Work on cell coordinates (odd indices) for corridors
        def carve(cx: int, cy: int):
            dirs = [(2,0),(-2,0),(0,2),(0,-2)]
            random.shuffle(dirs)
            for dx,dy in dirs:
                nx = cx + dx
                ny = cy + dy
                if 0 <= nx < w and 0 <= ny < h and not self.grid[nx][ny]:
                    # carve wall between
                    self.grid[cx + dx//2][cy + dy//2] = True
                    self.grid[nx][ny] = True
                    carve(nx, ny)

        # Ensure starting at an odd tile; if even-sized adjust
        sx = 1 if w > 2 else 0
        sy = 1 if h > 2 else 0
        # Mark starting cell open
        if sx < w and sy < h:
            self.grid[sx][sy] = True
            carve(sx, sy)

        # Make some random open tiles to avoid completely blocked small mazes
        for _ in range((w*h)//20):
            rx = random.randrange(0, w)
            ry = random.randrange(0, h)
            if 0 <= rx < w and 0 <= ry < h:
                self.grid[rx][ry] = True

        # Ensure borders may contain openings; but guarantee at least one open tile
        any_open = any(self.grid[x][y] for x in range(w) for y in range(h))
        if not any_open:
            self.grid[1][1] = True

    def is_open(self, x: int, y: int) -> bool:
        if 0 <= x < self.width and 0 <= y < self.height:
            return bool(self.grid[x][y])
        return False

    def neighbors(self, x: int, y: int) -> List[Tuple[int,int]]:
        out = []
        for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = x+dx, y+dy
            if 0 <= nx < self.width and 0 <= ny < self.height and self.is_open(nx,ny):
                out.append((nx,ny))
        return out

    def all_open_tiles(self) -> List[Tuple[int,int]]:
        tiles = []
        for x in range(self.width):
            for y in range(self.height):
                if self.grid[x][y]:
                    tiles.append((x,y))
        return tiles
