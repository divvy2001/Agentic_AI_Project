import sys
import os
from pathlib import Path
import random
import pygame
from typing import Set, Tuple

# Ensure package imports work when running as script or module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game.constants import (
    GRID_SIZE,
    CELL_SIZE,
    HUD_HEIGHT,
    WIDTH,
    HEIGHT,
    FPS,
    COLOR_BG,
    COLOR_GRID,
    COLOR_SNAKE,
    COLOR_FOOD,
    COLOR_HUD_TEXT,
    COLOR_GAME_OVER,
    DIRECTIONS,
)
from game.snake import Snake
from game.food import Food


def grid_to_pixels(pos: Tuple[int, int]) -> Tuple[int, int]:
    """Convert grid coordinate (x,y) to pixel top-left position inside window.

    Pixel Y includes HUD_HEIGHT offset.
    """
    x, y = pos
    return x * CELL_SIZE, HUD_HEIGHT + y * CELL_SIZE


class Game:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Snake")
        self.clock = pygame.time.Clock()
        self.font_score = pygame.font.Font(None, 36)
        self.font_controls = pygame.font.Font(None, 24)

        self.running = True
        self.new_game()

    def new_game(self) -> None:
        """Initialize or reset the game state."""
        mid_x = GRID_SIZE // 2
        mid_y = GRID_SIZE // 2
        # 3-length snake centered horizontally, head at the rightmost segment, moving right
        start_positions = [(mid_x - 1, mid_y), (mid_x, mid_y), (mid_x + 1, mid_y)]
        start_dir = DIRECTIONS['RIGHT']
        self.snake = Snake(start_positions, start_dir)
        self.food = Food(GRID_SIZE, GRID_SIZE)
        # ensure food not on snake
        exclude = set(self.snake.body)
        self.food.spawn(exclude)
        self.score = 0
        self.game_over = False
        print("RESTART", flush=True)

    def handle_key(self, key) -> None:
        if key == pygame.K_ESCAPE:
            print("QUIT", flush=True)
            self.running = False
            return
        if key == pygame.K_r:
            self.new_game()
            return
        if self.game_over:
            # ignore direction changes while game over
            return
        # Arrow keys
        mapping = {
            pygame.K_UP: 'UP',
            pygame.K_DOWN: 'DOWN',
            pygame.K_LEFT: 'LEFT',
            pygame.K_RIGHT: 'RIGHT',
        }
        if key in mapping:
            name = mapping[key]
            new_dir = DIRECTIONS[name]
            changed = self.snake.change_direction(new_dir)
            if changed:
                print(f"DIRECTION {name}", flush=True)

    def update(self) -> None:
        if self.game_over:
            return
        # Determine next head position
        hx, hy = self.snake.head()
        dx, dy = self.snake.dir
        next_head = (hx + dx, hy + dy)

        # Check collisions with wall
        if not (0 <= next_head[0] < GRID_SIZE and 0 <= next_head[1] < GRID_SIZE):
            self.game_over = True
            print("GAME OVER", flush=True)
            return

        # Check collision with self (any segment)
        if next_head in self.snake.body:
            self.game_over = True
            print("GAME OVER", flush=True)
            return

        # Check if next move will eat food
        if next_head == self.food.get_pos():
            # grow on move so the new head occupies the food cell and length increases immediately
            self.snake.grow_by_one()
            self.snake.move()
            self.score += 1
            print(f"SCORE:{self.score}", flush=True)
            # spawn new food excluding snake body
            exclude: Set[Tuple[int, int]] = set(self.snake.body)
            self.food.spawn(exclude)
            return

        # Normal move
        self.snake.move()

    def draw(self) -> None:
        # Background
        self.screen.fill(COLOR_BG)
        # HUD area
        # Draw score
        score_surf = self.font_score.render(f"Score: {self.score}", True, COLOR_HUD_TEXT)
        score_rect = score_surf.get_rect(midtop=(WIDTH // 2, 8))
        self.screen.blit(score_surf, score_rect)

        # Draw controls below score
        controls_text = "Controls: Arrow keys - move    R - restart    Esc - quit"
        ctrl_surf = self.font_controls.render(controls_text, True, COLOR_HUD_TEXT)
        ctrl_rect = ctrl_surf.get_rect(midtop=(WIDTH // 2, 44))
        self.screen.blit(ctrl_surf, ctrl_rect)

        # Draw grid area
        grid_top = HUD_HEIGHT
        # draw grid lines
        for x in range(GRID_SIZE + 1):
            px = x * CELL_SIZE
            pygame.draw.line(self.screen, COLOR_GRID, (px, grid_top), (px, grid_top + GRID_SIZE * CELL_SIZE))
        for y in range(GRID_SIZE + 1):
            py = grid_top + y * CELL_SIZE
            pygame.draw.line(self.screen, COLOR_GRID, (0, py), (GRID_SIZE * CELL_SIZE, py))

        # Draw food
        fx, fy = grid_to_pixels(self.food.get_pos())
        food_rect = pygame.Rect(fx + 1, fy + 1, CELL_SIZE - 2, CELL_SIZE - 2)
        pygame.draw.rect(self.screen, COLOR_FOOD, food_rect)

        # Draw snake
        for segment in self.snake.body:
            sx, sy = grid_to_pixels(segment)
            seg_rect = pygame.Rect(sx + 1, sy + 1, CELL_SIZE - 2, CELL_SIZE - 2)
            pygame.draw.rect(self.screen, COLOR_SNAKE, seg_rect)

        # If game over, display message
        if self.game_over:
            go_surf = self.font_score.render(f"GAME OVER - Final Score: {self.score}", True, COLOR_GAME_OVER)
            go_rect = go_surf.get_rect(center=(WIDTH // 2, HUD_HEIGHT + (GRID_SIZE * CELL_SIZE) // 2))
            self.screen.blit(go_surf, go_rect)

    def run(self) -> None:
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("QUIT", flush=True)
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event.key)

            # Update game state
            self.update()

            # Draw everything
            self.draw()
            pygame.display.flip()

            # Cap the frame rate
            self.clock.tick(FPS)

        pygame.quit()


if __name__ == "__main__":
    Game().run()
