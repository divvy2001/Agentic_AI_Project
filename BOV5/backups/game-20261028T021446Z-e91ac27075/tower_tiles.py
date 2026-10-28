"""
Tower Tiles - main game logic using pygame
Entry point: run this file to start the game.
Implements the Planner's requirements in a single module.
"""
import sys
import os
import math
import random
from pathlib import Path

# Ensure running as module or script works
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
from pygame.locals import *

# --- Configuration from Plan ---
WIDTH = 800
HEIGHT = 600
FPS = 60
COLS = 12
ROWS = 8
UI_HEIGHT = 40
STARTING_COINS = 150
STARTING_LIVES = 10
TOWER_COST = 50
TOWER_RANGE_TILES = 2.0
TOWER_SHOT_INTERVAL = 1.0  # seconds
BLOB_HP = 3
BLOB_REWARD = 20
TOTAL_WAVES = 5

# Colors
COLOR_BG = (50, 50, 60)
COLOR_UI = (30, 30, 40)
COLOR_PATH = (150, 100, 50)  # brown
COLOR_GRASS = (60, 150, 60)  # green
COLOR_GRID = (0, 0, 0)
COLOR_SELECTION = (255, 255, 255)
COLOR_TOWER = (200, 200, 200)
COLOR_BLOB = (160, 60, 200)  # purple
COLOR_PROJECTILE = (255, 220, 0)

# Implementation note: path is a continuous list of (col,row) from left edge to right edge
DEFAULT_PATH = [
    (0, 3), (1, 3), (2, 3), (2, 2), (3, 2), (4, 2), (4, 3), (5, 3), (6, 3),
    (6, 4), (7, 4), (8, 4), (8, 5), (9, 5), (10, 5), (11, 5)
]

# Helper
def clamp(v, a, b):
    return max(a, min(b, v))

class Blob:
    def __init__(self, path_pixels, path_tiles):
        # path_pixels: list of pixel centers to travel
        self.path_pixels = path_pixels
        self.path_tiles = path_tiles
        self.index = 0
        self.pos = pygame.Vector2(path_pixels[0])
        self.speed = 60.0  # pixels per second
        self.hp = BLOB_HP
        self.alive = True

    def update(self, dt):
        if not self.alive:
            return
        if self.index >= len(self.path_pixels)-1:
            # reached end
            return
        target = pygame.Vector2(self.path_pixels[self.index+1])
        dir = (target - self.pos)
        dist = dir.length()
        if dist < 1e-3:
            self.index += 1
            return
        dir = dir.normalize()
        move = dir * self.speed * dt
        if move.length() >= dist:
            self.pos = target
            self.index += 1
        else:
            self.pos += move

    def reached_end(self):
        return self.index >= len(self.path_pixels)-1 and (pygame.Vector2(self.path_pixels[-1]) - self.pos).length() < 1.0

class Tower:
    def __init__(self, col, row, center_px):
        self.col = col
        self.row = row
        self.center = pygame.Vector2(center_px)
        self.timer = 0.0

    def update(self, dt, blobs, projectiles, tile_size, grid_origin):
        self.timer += dt
        if self.timer >= TOWER_SHOT_INTERVAL:
            # find nearest blob within range (tile units)
            best = None
            best_dist = None
            for b in blobs:
                if not b.alive:
                    continue
                # compute distance in tile units
                # convert blob pos to tile coords
                blob_px = b.pos
                # tile position of tower
                tx = self.center.x
                ty = self.center.y
                dx = (blob_px.x - tx) / tile_size
                dy = (blob_px.y - ty) / tile_size
                d = math.hypot(dx, dy)
                if d <= TOWER_RANGE_TILES:
                    if best is None or d < best_dist:
                        best = b
                        best_dist = d
            if best is not None:
                # shoot projectile toward best
                proj = Projectile(self.center, best)
                projectiles.append(proj)
                self.timer = 0.0

class Projectile:
    def __init__(self, start_pos, target_blob):
        self.pos = pygame.Vector2(start_pos)
        self.target = target_blob
        self.speed = 300.0
        self.alive = True

    def update(self, dt):
        if not self.alive or not self.target.alive:
            self.alive = False
            return
        dir = pygame.Vector2(self.target.pos - self.pos)
        dist = dir.length()
        if dist < 1e-3:
            # hit
            self.hit_target()
            return
        dir = dir.normalize()
        move = dir * self.speed * dt
        if move.length() >= dist:
            # reach target
            self.pos = pygame.Vector2(self.target.pos)
            self.hit_target()
        else:
            self.pos += move

    def hit_target(self):
        if self.target.alive:
            self.target.hp -= 1
            if self.target.hp <= 0:
                self.target.alive = False
        self.alive = False

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Tower Tiles")  # Requirement 0: window title
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)

        self.tile_size = None
        self.grid_origin = None
        self.selection = [0, 0]

        self.reset_state()

    def reset_state(self):
        # initializes or resets all gameplay state
        self.coins = STARTING_COINS
        self.lives = STARTING_LIVES
        self.wave = 1
        self.blobs = []
        self.towers = []
        self.projectiles = []
        self.game_state = 'playing'  # can be 'playing', 'won', 'lost'
        self.selection = [0, 0]
        self.next_wave_countdown = 0.5  # small delay before first wave
        self.spawning = False
        self.spawn_timer = 0.0
        self.spawn_interval = 1.0
        self.spawned_in_wave = 0
        self.blobs_to_spawn = self.calc_blobs_for_wave(self.wave)
        # prepare path in pixel coords
        self.path_tiles = list(DEFAULT_PATH)
        self.compute_grid_geometry()
        self.path_pixels = [self.tile_center_px(c, r) for (c, r) in self.path_tiles]
        # prints
        print(f"[EVENT] COINS:{self.coins}", flush=True)
        print(f"[EVENT] LIVES:{self.lives}", flush=True)
        print(f"[EVENT] WAVE:{self.wave}", flush=True)

    def compute_grid_geometry(self):
        play_width = WIDTH
        play_height = HEIGHT - UI_HEIGHT
        tile_w = play_width // COLS
        tile_h = play_height // ROWS
        self.tile_size = min(tile_w, tile_h)
        grid_width = self.tile_size * COLS
        grid_height = self.tile_size * ROWS
        # center grid horizontally
        origin_x = (WIDTH - grid_width) // 2
        origin_y = UI_HEIGHT + (play_height - grid_height) // 2
        self.grid_origin = (origin_x, origin_y)

    def tile_rect(self, col, row):
        ox, oy = self.grid_origin
        return pygame.Rect(ox + col*self.tile_size, oy + row*self.tile_size, self.tile_size, self.tile_size)

    def tile_center_px(self, col, row):
        r = self.tile_rect(col, row)
        return (r.x + r.w/2, r.y + r.h/2)

    def is_path_tile(self, col, row):
        return (col, row) in self.path_tiles

    def calc_blobs_for_wave(self, wave):
        # simple progression
        return 4 + wave * 2

    # Public API per contract
    def restart(self):
        self.reset_state()
        print("RESTART", flush=True)

    def send_next_wave(self):
        if self.game_state != 'playing':
            return
        if not self.spawning and self.wave <= TOTAL_WAVES:
            # start spawning immediately
            self.spawning = True
            self.spawned_in_wave = 0
            self.blobs_to_spawn = self.calc_blobs_for_wave(self.wave)
            self.spawn_timer = 0.0
            print("NEXT WAVE", flush=True)
            print(f"[EVENT] WAVE:{self.wave}", flush=True)

    def build_tower(self, col, row):
        if self.is_path_tile(col, row):
            return False
        # check existing tower
        for t in self.towers:
            if t.col == col and t.row == row:
                return False
        if self.coins < TOWER_COST:
            return False
        # charge
        self.coins -= TOWER_COST
        print("BUILD", flush=True)
        print(f"[EVENT] COINS:{self.coins}", flush=True)
        center = self.tile_center_px(col, row)
        self.towers.append(Tower(col, row, center))
        return True

    def handle_key(self, key):
        if key == K_RIGHT:
            old = list(self.selection)
            self.selection[0] = clamp(self.selection[0]+1, 0, COLS-1)
            if self.selection != old:
                print("MOVE RIGHT", flush=True)
        elif key == K_LEFT:
            old = list(self.selection)
            self.selection[0] = clamp(self.selection[0]-1, 0, COLS-1)
            if self.selection != old:
                print("MOVE LEFT", flush=True)
        elif key == K_UP:
            old = list(self.selection)
            self.selection[1] = clamp(self.selection[1]-1, 0, ROWS-1)
            if self.selection != old:
                print("MOVE UP", flush=True)
        elif key == K_DOWN:
            old = list(self.selection)
            self.selection[1] = clamp(self.selection[1]+1, 0, ROWS-1)
            if self.selection != old:
                print("MOVE DOWN", flush=True)
        elif key == K_SPACE:
            col, row = self.selection
            built = self.build_tower(col, row)
            # print BUILD is handled inside build_tower when successful
        elif key == K_n:
            # send next wave early
            if self.game_state == 'playing':
                # if currently between waves (not spawning) start spawning
                if not self.spawning:
                    self.send_next_wave()
                else:
                    # if already spawning, pressing N has no effect
                    pass
        elif key == K_r:
            self.restart()
        elif key == K_ESCAPE:
            print("QUIT", flush=True)
            pygame.quit()
            sys.exit(0)

    def update(self, dt):
        if self.game_state != 'playing':
            return
        # spawning logic
        if self.spawning:
            self.spawn_timer += dt
            if self.spawned_in_wave < self.blobs_to_spawn and self.spawn_timer >= self.spawn_interval:
                # spawn a blob
                b = Blob(self.path_pixels, self.path_tiles)
                self.blobs.append(b)
                self.spawned_in_wave += 1
                self.spawn_timer = 0.0
            # if finished spawning for this wave and there are no blobs left, end wave
            if self.spawned_in_wave >= self.blobs_to_spawn and all(not b.alive for b in self.blobs):
                # wave cleared
                self.spawning = False
                if self.wave >= TOTAL_WAVES:
                    # win
                    self.game_state = 'won'
                    print('WIN', flush=True)
                else:
                    # prepare next wave after countdown
                    self.wave += 1
                    self.next_wave_countdown = 5.0
                    print(f"[EVENT] WAVE:{self.wave}", flush=True)
        else:
            # between waves countdown
            if self.next_wave_countdown > 0:
                self.next_wave_countdown -= dt
                if self.next_wave_countdown <= 0 and self.wave <= TOTAL_WAVES:
                    # start spawning
                    self.spawning = True
                    self.spawned_in_wave = 0
                    self.blobs_to_spawn = self.calc_blobs_for_wave(self.wave)
                    self.spawn_timer = 0.0

        # update blobs
        for b in self.blobs:
            if b.alive:
                b.update(dt)
                if b.reached_end() and b.alive:
                    b.alive = False
                    self.lives -= 1
                    print(f"[EVENT] LIVES:{self.lives}", flush=True)
                    if self.lives <= 0:
                        self.game_state = 'lost'
                        print('GAME OVER', flush=True)
        # update towers (they may append projectiles)
        for t in self.towers:
            t.update(dt, self.blobs, self.projectiles, self.tile_size, self.grid_origin)
        # update projectiles
        for p in self.projectiles:
            p.update(dt)
        # cleanup projectiles and dead blobs
        self.projectiles = [p for p in self.projectiles if p.alive]
        removed = [b for b in self.blobs if not b.alive]
        # reward for blobs that died by damage (hp<=0) but only if they died by being marked not alive and not by reaching end
        # we detect reward by checking hp<=0
        for b in removed:
            if b.hp <= 0:
                self.coins += BLOB_REWARD
                print(f"[EVENT] COINS:{self.coins}", flush=True)
        # keep only alive blobs
        self.blobs = [b for b in self.blobs if b.alive]

    def draw(self):
        self.screen.fill(COLOR_BG)
        # UI bar
        pygame.draw.rect(self.screen, COLOR_UI, (0, 0, WIDTH, UI_HEIGHT))
        # draw text: coins, lives, wave
        coins_surf = self.font.render(f"Coins: {self.coins}", True, (255, 255, 255))
        lives_surf = self.font.render(f"Lives: {self.lives}", True, (255, 255, 255))
        wave_surf = self.font.render(f"Wave: {self.wave}", True, (255, 255, 255))
        self.screen.blit(coins_surf, (10, 8))
        self.screen.blit(lives_surf, (200, 8))
        self.screen.blit(wave_surf, (350, 8))

        # grid background
        ox, oy = self.grid_origin
        for r in range(ROWS):
            for c in range(COLS):
                rect = pygame.Rect(ox + c*self.tile_size, oy + r*self.tile_size, self.tile_size, self.tile_size)
                if self.is_path_tile(c, r):
                    color = COLOR_PATH
                else:
                    color = COLOR_GRASS
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, COLOR_GRID, rect, 1)
        # draw towers
        for t in self.towers:
            rect = self.tile_rect(t.col, t.row)
            center = rect.center
            pygame.draw.circle(self.screen, COLOR_TOWER, center, max(4, self.tile_size//3))
        # draw path blobs along path
        for b in self.blobs:
            if b.alive:
                pygame.draw.circle(self.screen, COLOR_BLOB, (int(b.pos.x), int(b.pos.y)), max(4, self.tile_size//4))
                # draw HP
                hp_s = self.font.render(str(b.hp), True, (255, 255, 255))
                self.screen.blit(hp_s, (b.pos.x - 6, b.pos.y - 18))
        # draw projectiles
        for p in self.projectiles:
            pygame.draw.circle(self.screen, COLOR_PROJECTILE, (int(p.pos.x), int(p.pos.y)), 4)
        # draw selection square
        sel_rect = self.tile_rect(self.selection[0], self.selection[1])
        pygame.draw.rect(self.screen, COLOR_SELECTION, sel_rect, 3)

        # end game messages
        if self.game_state == 'won':
            win_surf = self.font.render('WIN', True, (255, 255, 0))
            self.screen.blit(win_surf, (WIDTH//2 - 20, UI_HEIGHT + 10))
        elif self.game_state == 'lost':
            go_surf = self.font.render('GAME OVER', True, (255, 50, 50))
            self.screen.blit(go_surf, (WIDTH//2 - 50, UI_HEIGHT + 10))

        pygame.display.flip()

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == QUIT:
                    print("QUIT", flush=True)
                    running = False
                elif event.type == KEYDOWN:
                    if event.key == K_ESCAPE:
                        print("QUIT", flush=True)
                        running = False
                    else:
                        # handle keys
                        self.handle_key(event.key)
            # update
            self.update(dt)
            # draw
            self.draw()
        pygame.quit()


if __name__ == '__main__':
    g = Game()
    g.run()
