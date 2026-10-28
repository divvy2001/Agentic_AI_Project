import sys
import os
import pygame
from pathlib import Path
from typing import Tuple, List

# Ensure package imports work for both python -m and direct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game.maze import Maze
from game.entities import Mouse, Cat, Crumb

# Game settings from Plan
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
FPS = 60
MAZE_W = 15
MAZE_H = 15
HUD_HEIGHT = 40
MARGIN = 20

class CrumbChaseGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption('Crumb Chase')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)

        # Maze and layout
        self.maze = Maze(MAZE_W, MAZE_H)
        # Compute tile size to fit
        available_w = WINDOW_WIDTH - 2 * MARGIN
        available_h = WINDOW_HEIGHT - HUD_HEIGHT - 2 * MARGIN
        self.tile_size = min(available_w // MAZE_W, available_h // MAZE_H)
        self.origin_x = MARGIN + (available_w - self.tile_size * MAZE_W) // 2
        self.origin_y = HUD_HEIGHT + MARGIN + (available_h - self.tile_size * MAZE_H) // 2

        # Game state
        self.score = 0
        self.lives = 3
        self.state = 'PLAY'  # PLAY, WIN, GAME_OVER

        # Entities (start tiles assigned after maze created)
        self.mouse: Mouse = None
        self.cats: List[Cat] = []
        self.crumbs: List[Crumb] = []

        self.reset_game()

    def find_open_nearest(self, prefer: Tuple[int,int]) -> Tuple[int,int]:
        # find an open tile nearest to prefer
        opens = self.maze.all_open_tiles()
        if not opens:
            return (0,0)
        best = opens[0]
        best_dist = abs(best[0]-prefer[0]) + abs(best[1]-prefer[1])
        for t in opens:
            d = abs(t[0]-prefer[0]) + abs(t[1]-prefer[1])
            if d < best_dist:
                best = t
                best_dist = d
        return best

    def reset_game(self):
        # Rebuild maze and entities
        self.maze.reset()
        # Score and lives
        self.score = 0
        self.lives = 3
        self.state = 'PLAY'

        # Choose start positions (mouse center, cats corners)
        mouse_start = self.find_open_nearest((MAZE_W//2, MAZE_H//2))
        cat1_start = self.find_open_nearest((0,0))
        cat2_start = self.find_open_nearest((MAZE_W-1, MAZE_H-1))

        self.mouse = Mouse(mouse_start, self.tile_size, speed_tiles_per_sec=6.0)
        self.mouse.initialize_position(self.origin_x, self.origin_y)
        self.cats = [
            Cat(cat1_start, self.tile_size, speed_tiles_per_sec=3.0),
            Cat(cat2_start, self.tile_size, speed_tiles_per_sec=3.0)
        ]
        for c in self.cats:
            c.initialize_position(self.origin_x, self.origin_y)

        # Create crumbs on every open tile
        self.crumbs = []
        for t in self.maze.all_open_tiles():
            self.crumbs.append(Crumb(t))

    def eat_crumb_at(self, tile: Tuple[int,int]):
        for crumb in self.crumbs:
            if crumb.tile == tile and not crumb.eaten:
                ate = crumb.eat()
                if ate:
                    self.score += 10
                    # Print score event
                    print(f"[EVENT] SCORE:{self.score}", flush=True)
                    # Check win
                    if all(c.eaten for c in self.crumbs):
                        self.state = 'WIN'
                        print('WIN', flush=True)
                return

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                print('QUIT', flush=True)
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    print('QUIT', flush=True)
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_r:
                    # Restart
                    print('RESTART', flush=True)
                    self.reset_game()
                if self.state != 'PLAY':
                    # while frozen, only R and ESC act
                    continue
                if event.key == pygame.K_UP:
                    self.mouse.set_dir(0, -1, self.maze)
                    print('TURN UP', flush=True)
                elif event.key == pygame.K_DOWN:
                    self.mouse.set_dir(0, 1, self.maze)
                    print('TURN DOWN', flush=True)
                elif event.key == pygame.K_LEFT:
                    self.mouse.set_dir(-1, 0, self.maze)
                    print('TURN LEFT', flush=True)
                elif event.key == pygame.K_RIGHT:
                    self.mouse.set_dir(1, 0, self.maze)
                    print('TURN RIGHT', flush=True)

    def update(self, dt: float):
        if self.state != 'PLAY':
            return
        # Update mouse
        prev_tile = self.mouse.current_tile()
        self.mouse.update(dt, self.maze, self.origin_x, self.origin_y)
        new_tile = self.mouse.current_tile()
        if new_tile != prev_tile:
            # Mouse moved onto new tile: attempt to eat crumb
            self.eat_crumb_at(new_tile)

        # Update cats
        mouse_tile = self.mouse.current_tile()
        for cat in self.cats:
            cat.update(dt, self.maze, mouse_tile, self.origin_x, self.origin_y)

        # Check collisions
        for cat in self.cats:
            if cat.current_tile() == self.mouse.current_tile():
                # collision
                self.lives -= 1
                if self.lives <= 0:
                    self.state = 'GAME_OVER'
                    print('GAME OVER', flush=True)
                # teleport everyone to starts
                self.mouse.teleport(self.mouse.start_tile, self.origin_x, self.origin_y)
                for c in self.cats:
                    c.teleport(c.start_tile, self.origin_x, self.origin_y)
                break

    def draw(self):
        self.screen.fill((0,0,0))
        # HUD background
        pygame.draw.rect(self.screen, (30,30,30), (0,0, WINDOW_WIDTH, HUD_HEIGHT))
        # HUD text
        hud_text = self.font.render(f"Score: {self.score}   Lives: {self.lives}", True, (255,255,255))
        self.screen.blit(hud_text, (10, 10))

        # Draw maze tiles
        for x in range(self.maze.width):
            for y in range(self.maze.height):
                tx = self.origin_x + x * self.tile_size
                ty = self.origin_y + y * self.tile_size
                rect = pygame.Rect(tx, ty, self.tile_size, self.tile_size)
                if self.maze.is_open(x,y):
                    pygame.draw.rect(self.screen, (20,20,20), rect)
                else:
                    pygame.draw.rect(self.screen, (70,70,70), rect)
                # tile grid lines
                pygame.draw.rect(self.screen, (40,40,40), rect, 1)

        # Draw crumbs
        for crumb in self.crumbs:
            if not crumb.eaten and self.maze.is_open(crumb.tile[0], crumb.tile[1]):
                cx = self.origin_x + crumb.tile[0]*self.tile_size + self.tile_size//2
                cy = self.origin_y + crumb.tile[1]*self.tile_size + self.tile_size//2
                r = max(2, self.tile_size//8)
                pygame.draw.circle(self.screen, (255,215,0), (int(cx), int(cy)), r)

        # Draw cats
        colors = [(200,50,50),(50,50,200)]
        for i,cat in enumerate(self.cats):
            pygame.draw.circle(self.screen, colors[i%len(colors)], (int(cat.px), int(cat.py)), max(4, self.tile_size//3))

        # Draw mouse (green)
        pygame.draw.circle(self.screen, (50,200,50), (int(self.mouse.px), int(self.mouse.py)), max(4, self.tile_size//3))

        # If win or game over, display message and final score
        if self.state == 'WIN':
            s = self.font.render(f"WIN - Final Score: {self.score}", True, (255,255,255))
            rect = s.get_rect(center=(WINDOW_WIDTH//2, HUD_HEIGHT//2))
            self.screen.blit(s, rect)
        elif self.state == 'GAME_OVER':
            s = self.font.render(f"GAME OVER - Final Score: {self.score}", True, (255,255,255))
            rect = s.get_rect(center=(WINDOW_WIDTH//2, HUD_HEIGHT//2))
            self.screen.blit(s, rect)

        pygame.display.flip()

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()


def main():
    game = CrumbChaseGame()
    game.run()

if __name__ == '__main__':
    main()
