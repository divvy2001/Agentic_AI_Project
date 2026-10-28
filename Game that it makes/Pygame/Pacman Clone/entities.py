import math
import random
from typing import Optional, Tuple, List
from game.maze import Maze

class Mouse:
    def __init__(self, start_tile: Tuple[int,int], tile_size: int, speed_tiles_per_sec: float = 6.0):
        self.start_tile = start_tile
        self.tile_size = tile_size
        self.speed_tiles_per_sec = speed_tiles_per_sec
        self.tile = start_tile
        self.dir: Optional[Tuple[int,int]] = None
        self.target_tile: Optional[Tuple[int,int]] = None
        self.px, self.py = 0.0, 0.0

    def initialize_position(self, origin_x: int, origin_y: int):
        tx, ty = self.tile
        self.px = origin_x + tx * self.tile_size + self.tile_size/2
        self.py = origin_y + ty * self.tile_size + self.tile_size/2
        self.target_tile = None
        self.dir = None

    def set_dir(self, dx: int, dy: int, maze: Maze):
        # set intended direction; if immediate neighbor in that dir is open start moving
        self.dir = (dx,dy)
        nx = self.tile[0] + dx
        ny = self.tile[1] + dy
        if maze.is_open(nx, ny):
            self.target_tile = (nx, ny)
        else:
            # cannot move into wall; stay but keep dir so future tiles might open
            self.target_tile = None

    def teleport(self, tile: Tuple[int,int], origin_x: int, origin_y: int):
        self.tile = tile
        self.start_tile = tile
        self.px = origin_x + tile[0] * self.tile_size + self.tile_size/2
        self.py = origin_y + tile[1] * self.tile_size + self.tile_size/2
        self.dir = None
        self.target_tile = None

    def current_tile(self) -> Tuple[int,int]:
        return self.tile

    def update(self, dt: float, maze: Maze, origin_x: int, origin_y: int):
        # If no current movement but a dir exists, attempt to set target
        if self.target_tile is None and self.dir is not None:
            nx = self.tile[0] + self.dir[0]
            ny = self.tile[1] + self.dir[1]
            if maze.is_open(nx, ny):
                self.target_tile = (nx, ny)
            else:
                # blocked
                self.target_tile = None
                return
        if self.target_tile is None:
            return
        # Move towards target tile center
        tx, ty = self.target_tile
        target_x = origin_x + tx * self.tile_size + self.tile_size/2
        target_y = origin_y + ty * self.tile_size + self.tile_size/2
        vx = target_x - self.px
        vy = target_y - self.py
        dist = math.hypot(vx, vy)
        if dist == 0:
            # arrived
            self.tile = self.target_tile
            # after arriving, try to continue in same dir
            next_tx = self.tile[0] + (self.dir[0] if self.dir else 0)
            next_ty = self.tile[1] + (self.dir[1] if self.dir else 0)
            if self.dir and maze.is_open(next_tx, next_ty):
                self.target_tile = (next_tx, next_ty)
            else:
                self.target_tile = None
            return
        speed = self.speed_tiles_per_sec * self.tile_size
        travel = speed * dt
        if travel >= dist:
            # snap to target
            self.px = target_x
            self.py = target_y
            self.tile = self.target_tile
            # continue in same dir if possible
            next_tx = self.tile[0] + (self.dir[0] if self.dir else 0)
            next_ty = self.tile[1] + (self.dir[1] if self.dir else 0)
            if self.dir and maze.is_open(next_tx, next_ty):
                self.target_tile = (next_tx, next_ty)
            else:
                self.target_tile = None
        else:
            # move proportionally
            self.px += (vx / dist) * travel
            self.py += (vy / dist) * travel

class Cat:
    def __init__(self, start_tile: Tuple[int,int], tile_size: int, speed_tiles_per_sec: float = 3.0):
        self.start_tile = start_tile
        self.tile_size = tile_size
        self.speed_tiles_per_sec = speed_tiles_per_sec
        self.tile = start_tile
        self.target_tile: Optional[Tuple[int,int]] = None
        self.prev_tile: Optional[Tuple[int,int]] = None
        self.px, self.py = 0.0, 0.0

    def initialize_position(self, origin_x: int, origin_y: int):
        tx, ty = self.tile
        self.px = origin_x + tx * self.tile_size + self.tile_size/2
        self.py = origin_y + ty * self.tile_size + self.tile_size/2
        self.target_tile = None
        self.prev_tile = None

    def teleport(self, tile: Tuple[int,int], origin_x: int, origin_y: int):
        self.tile = tile
        self.start_tile = tile
        self.px = origin_x + tile[0] * self.tile_size + self.tile_size/2
        self.py = origin_y + tile[1] * self.tile_size + self.tile_size/2
        self.target_tile = None
        self.prev_tile = None

    def current_tile(self) -> Tuple[int,int]:
        return self.tile

    def choose_next(self, maze: Maze, mouse_tile: Tuple[int,int]):
        # Choose next tile at junctions toward mouse
        neigh = maze.neighbors(self.tile[0], self.tile[1])
        if not neigh:
            return None
        # prefer not going back to prev_tile
        options = [n for n in neigh if n != self.prev_tile]
        if not options:
            options = neigh
        # If at a junction (>2 open paths), pick neighbor that reduces Manhattan distance
        best = None
        best_dist = None
        mx, my = mouse_tile
        for n in options:
            dist = abs(n[0]-mx) + abs(n[1]-my)
            if best is None or dist < best_dist:
                best = n
                best_dist = dist
        return best

    def update(self, dt: float, maze: Maze, mouse_tile: Tuple[int,int], origin_x: int, origin_y: int):
        # If not moving, pick next
        if self.target_tile is None:
            choice = self.choose_next(maze, mouse_tile)
            if choice is not None:
                self.target_tile = choice
            else:
                return
        # Move towards target tile center
        tx, ty = self.target_tile
        target_x = origin_x + tx * self.tile_size + self.tile_size/2
        target_y = origin_y + ty * self.tile_size + self.tile_size/2
        vx = target_x - self.px
        vy = target_y - self.py
        dist = math.hypot(vx, vy)
        if dist == 0:
            # arrived
            self.prev_tile = self.tile
            self.tile = self.target_tile
            self.target_tile = None
            return
        speed = self.speed_tiles_per_sec * self.tile_size
        travel = speed * dt
        if travel >= dist:
            self.px = target_x
            self.py = target_y
            self.prev_tile = self.tile
            self.tile = self.target_tile
            self.target_tile = None
        else:
            self.px += (vx / dist) * travel
            self.py += (vy / dist) * travel

class Crumb:
    def __init__(self, tile: Tuple[int,int]):
        self.tile = tile
        self.eaten = False

    def eat(self):
        if not self.eaten:
            self.eaten = True
            return True
        return False
