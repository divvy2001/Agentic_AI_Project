import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
import random
from typing import Tuple

from constants import *
from snake import Snake
from food import Food


def create_initial_snake() -> Snake:
    center_x = GRID_SIZE // 2
    center_y = GRID_SIZE // 2
    # head first, moving right
    initial = [ (center_x + 1, center_y), (center_x, center_y), (center_x - 1, center_y) ]
    return Snake(initial, DIR_RIGHT)


def init_game(state: dict) -> None:
    state['snake'] = create_initial_snake()
    state['food'] = Food(GRID_SIZE)
    state['food'].respawn(state['snake'].occupies())
    state['score'] = 0
    state['game_over'] = False


def draw_grid(surface: pygame.Surface) -> None:
    # play area background
    play_rect = pygame.Rect(0, TOP_MARGIN, PLAY_WIDTH, PLAY_WIDTH)
    surface.fill(BG_COLOR)
    pygame.draw.rect(surface, LIGHT_GRAY, play_rect)
    # draw grid lines
    for i in range(GRID_SIZE + 1):
        x = i * CELL_SIZE
        pygame.draw.line(surface, GRAY, (x, TOP_MARGIN), (x, TOP_MARGIN + PLAY_WIDTH))
        y = TOP_MARGIN + i * CELL_SIZE
        pygame.draw.line(surface, GRAY, (0, y), (PLAY_WIDTH, y))


def grid_to_pixel(pos: Tuple[int,int]) -> pygame.Rect:
    x, y = pos
    return pygame.Rect(x * CELL_SIZE, TOP_MARGIN + y * CELL_SIZE, CELL_SIZE, CELL_SIZE)


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Snake")
    clock = pygame.time.Clock()

    score_font = pygame.font.Font(None, SCORE_FONT_SIZE)
    ctrl_font = pygame.font.Font(None, CTRL_FONT_SIZE)
    gameover_font = pygame.font.Font(None, GAMEOVER_FONT_SIZE)

    state = {}
    init_game(state)

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    init_game(state)
                elif not state.get('game_over', False):
                    if event.key == pygame.K_UP:
                        state['snake'].set_direction(*DIR_UP)
                    elif event.key == pygame.K_DOWN:
                        state['snake'].set_direction(*DIR_DOWN)
                    elif event.key == pygame.K_LEFT:
                        state['snake'].set_direction(*DIR_LEFT)
                    elif event.key == pygame.K_RIGHT:
                        state['snake'].set_direction(*DIR_RIGHT)

        # Update
        if not state.get('game_over', False):
            # Move snake
            snake: Snake = state['snake']
            next_pos = snake.next_head()
            # Check wall collision
            nx, ny = next_pos
            if nx < 0 or nx >= GRID_SIZE or ny < 0 or ny >= GRID_SIZE:
                state['game_over'] = True
                print("GAME OVER")
            else:
                # Check if eating
                grow = (next_pos == state['food'].position)
                # Check self collision
                if snake.check_self_collision(next_pos, grow=grow):
                    state['game_over'] = True
                    print("GAME OVER")
                else:
                    snake.move(grow=grow)
                    if grow:
                        state['score'] += 1
                        print(state['score'])
                        # Spawn new food
                        state['food'].respawn(snake.occupies())

        # Draw
        draw_grid(screen)

        # Draw food
        food_rect = grid_to_pixel(state['food'].position)
        pygame.draw.rect(screen, FOOD_COLOR, food_rect)

        # Draw snake
        for segment in state['snake'].body:
            r = grid_to_pixel(segment)
            pygame.draw.rect(screen, SNAKE_COLOR, r)

        # Draw score and controls
        score_surf = score_font.render(f"Score: {state['score']}", True, WHITE)
        screen.blit(score_surf, (10, 10))
        ctrl_surf = ctrl_font.render("Arrows: Move   R: Restart   Esc: Quit", True, WHITE)
        screen.blit(ctrl_surf, (10, 40))

        # If game over, overlay message and freeze snake
        if state.get('game_over', False):
            go_surf = gameover_font.render("GAME OVER", True, FOOD_COLOR)
            go_rect = go_surf.get_rect(center=(PLAY_WIDTH // 2, TOP_MARGIN // 2 + 10))
            screen.blit(go_surf, go_rect)

            final_surf = score_font.render(f"Final Score: {state['score']}", True, WHITE)
            final_rect = final_surf.get_rect(center=(PLAY_WIDTH // 2, TOP_MARGIN // 2 + 40))
            screen.blit(final_surf, final_rect)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == '__main__':
    main()
