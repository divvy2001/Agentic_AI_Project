import sys
import os
# Ensure sibling imports work when running as a module or script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
from pathlib import Path
from typing import Tuple

from game.constants import (
    RESOLUTION_WIDTH,
    RESOLUTION_HEIGHT,
    FPS,
    GRID_SIZE,
    CELL_SIZE,
    UI_HEIGHT,
    BG_COLOR,
    UI_BG_COLOR,
    GRID_COLOR,
    SNAKE_COLOR,
    FOOD_COLOR,
    TEXT_COLOR,
    CONTROLS_TEXT,
)
from game.snake import Snake
from game.food import Food


def grid_to_pixel(cell: Tuple[int, int]) -> Tuple[int, int]:
    x, y = cell
    px = x * CELL_SIZE
    py = UI_HEIGHT + y * CELL_SIZE
    return px, py


def draw_grid(surface: pygame.Surface) -> None:
    # draw background for grid area
    grid_rect = pygame.Rect(0, UI_HEIGHT, CELL_SIZE * GRID_SIZE, CELL_SIZE * GRID_SIZE)
    pygame.draw.rect(surface, BG_COLOR, grid_rect)
    # draw grid lines
    for x in range(GRID_SIZE + 1):
        pygame.draw.line(surface, GRID_COLOR, (x * CELL_SIZE, UI_HEIGHT), (x * CELL_SIZE, UI_HEIGHT + CELL_SIZE * GRID_SIZE))
    for y in range(GRID_SIZE + 1):
        pygame.draw.line(surface, GRID_COLOR, (0, UI_HEIGHT + y * CELL_SIZE), (CELL_SIZE * GRID_SIZE, UI_HEIGHT + y * CELL_SIZE))


def main():
    pygame.init()
    screen = pygame.display.set_mode((RESOLUTION_WIDTH, RESOLUTION_HEIGHT))
    pygame.display.set_caption("Snake")
    clock = pygame.time.Clock()

    font_score = pygame.font.Font(None, 36)
    font_controls = pygame.font.Font(None, 24)

    # Initialize game objects
    snake = Snake()
    food = Food(snake.get_positions())
    score = 0
    game_over = False

    running = True

    # Helper to print score changes as required
    def set_score(new_score: int):
        nonlocal score
        score = new_score
        print(f"SCORE:{score}", flush=True)

    # Direction name mapping
    DIR_NAMES = {
        (1, 0): "RIGHT",
        (-1, 0): "LEFT",
        (0, 1): "DOWN",
        (0, -1): "UP",
    }

    while running:
        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                print("QUIT", flush=True)
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    print("QUIT", flush=True)
                    running = False
                elif event.key == pygame.K_r:
                    # Restart
                    snake.reset()
                    food.spawn(snake.get_positions())
                    score = 0
                    game_over = False
                    print("RESTART", flush=True)
                elif event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                    key_dir = {
                        pygame.K_UP: (0, -1),
                        pygame.K_DOWN: (0, 1),
                        pygame.K_LEFT: (-1, 0),
                        pygame.K_RIGHT: (1, 0),
                    }[event.key]
                    prev_dir = snake.direction
                    snake.set_direction(*key_dir)
                    # Print direction only if it actually changed
                    if snake.direction != prev_dir:
                        name = DIR_NAMES.get(snake.direction, str(snake.direction))
                        print(f"DIRECTION {name}", flush=True)

        # Update game state once per frame (FPS controls speed)
        if not game_over:
            # Predict next head
            head_x, head_y = snake.head()
            dx, dy = snake.direction
            next_head = (head_x + dx, head_y + dy)

            # Check wall collision
            if not (0 <= next_head[0] < GRID_SIZE and 0 <= next_head[1] < GRID_SIZE):
                game_over = True
                print("GAME OVER", flush=True)
            else:
                # Will eating occur?
                will_eat = (food.get_position() == next_head)

                # Self-collision check: moving into body is collision, except moving into tail which will move away when not growing
                positions = snake.get_positions()
                tail = positions[0]
                if next_head in positions:
                    if not (not will_eat and next_head == tail):
                        game_over = True
                        print("GAME OVER", flush=True)
                        # Do not perform move
                    else:
                        # Allowed: moving into tail when not growing
                        snake.move(grow=will_eat)
                else:
                    # Safe to move
                    snake.move(grow=will_eat)

                # After moving, if we ate food handle growth/score/spawn
                if will_eat and not game_over:
                    set_score(score + 1)
                    food.spawn(snake.get_positions())

        # Rendering
        screen.fill(UI_BG_COLOR)
        # Draw score at top
        score_surf = font_score.render(f"Score: {score}", True, TEXT_COLOR)
        screen.blit(score_surf, (10, 10))
        # Draw controls below score
        controls_surf = font_controls.render(CONTROLS_TEXT, True, TEXT_COLOR)
        screen.blit(controls_surf, (10, 50))

        # Draw grid and items
        draw_grid(screen)

        # Draw food
        fpos = food.get_position()
        if fpos is not None:
            fx, fy = grid_to_pixel(fpos)
            rect = pygame.Rect(fx + 1, fy + 1, CELL_SIZE - 1, CELL_SIZE - 1)
            pygame.draw.rect(screen, FOOD_COLOR, rect)

        # Draw snake
        for pos in snake.get_positions():
            sx, sy = grid_to_pixel(pos)
            rect = pygame.Rect(sx + 1, sy + 1, CELL_SIZE - 1, CELL_SIZE - 1)
            pygame.draw.rect(screen, SNAKE_COLOR, rect)

        # If game over, overlay GAME OVER text and final score
        if game_over:
            go_surf = font_score.render("GAME OVER", True, (255, 50, 50))
            go_rect = go_surf.get_rect(center=(RESOLUTION_WIDTH // 2, UI_HEIGHT // 2))
            screen.blit(go_surf, go_rect)
            final_surf = font_controls.render(f"Final Score: {score}", True, TEXT_COLOR)
            final_rect = final_surf.get_rect(center=(RESOLUTION_WIDTH // 2, UI_HEIGHT // 2 + 30))
            screen.blit(final_surf, final_rect)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == '__main__':
    main()
