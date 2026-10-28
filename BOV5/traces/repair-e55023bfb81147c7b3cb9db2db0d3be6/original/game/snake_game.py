import sys
import os
import pygame
from typing import Tuple

# Ensure local imports work when running as module or script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from snake import Snake
from food import Food

# Game configuration from Plan
GRID_SIZE = 20
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 680
HEADER_HEIGHT = 80  # space for score and controls
CELL_SIZE = WINDOW_WIDTH // GRID_SIZE  # 30
FPS = 10

# Colors
BG_COLOR = (40, 40, 40)
GRID_COLOR = (60, 60, 60)
SNAKE_COLOR = (0, 200, 0)
FOOD_COLOR = (200, 0, 0)
TEXT_COLOR = (230, 230, 230)
GAME_OVER_COLOR = (200, 50, 50)

KEY_DIR = {
    pygame.K_UP: 'UP',
    pygame.K_DOWN: 'DOWN',
    pygame.K_LEFT: 'LEFT',
    pygame.K_RIGHT: 'RIGHT',
}


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption('Snake')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 28)
        self.large_font = pygame.font.Font(None, 64)

        self.snake = Snake()
        self.food = Food(grid_size=GRID_SIZE)

        self.score = 0
        self.game_over = False

        self.reset()

    def reset(self):
        # Centered 3-length snake moving RIGHT. Head is first element.
        center_x = GRID_SIZE // 2
        center_y = GRID_SIZE // 2
        start_positions = [(center_x, center_y), (center_x - 1, center_y), (center_x - 2, center_y)]
        self.snake.reset(start_positions, 'RIGHT')
        self.food.spawn(self.snake.get_positions())
        old_score = self.score
        self.score = 0
        self.game_over = False
        if self.score != old_score:
            print(f"[EVENT] SCORE:{self.score}")

    def handle_key(self, key):
        if key in KEY_DIR:
            self.snake.change_direction(KEY_DIR[key])
        elif key == pygame.K_r:
            self.reset()
        elif key == pygame.K_ESCAPE:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    def update(self):
        if self.game_over:
            return
        # Advance snake by one
        self.snake.update()
        head = self.snake.get_head()
        hx, hy = head
        # Check wall collision
        if not (0 <= hx < GRID_SIZE and 0 <= hy < GRID_SIZE):
            self.game_over = True
            print("GAME OVER")
            return
        # Check self collision
        if self.snake.is_collision_with_self():
            self.game_over = True
            print("GAME OVER")
            return
        # Check food collision
        food_pos = self.food.get_position()
        if food_pos is not None and head == food_pos:
            # Grow by one for next move
            self.snake.grow(1)
            # Update score and print event
            self.score += 1
            print(f"[EVENT] SCORE:{self.score}")
            # Spawn new food excluding current snake positions
            self.food.spawn(self.snake.get_positions())

    def draw_grid(self):
        # background
        self.screen.fill(BG_COLOR)
        # header area background
        pygame.draw.rect(self.screen, (30, 30, 30), (0, 0, WINDOW_WIDTH, HEADER_HEIGHT))
        # draw grid lines and cells area
        for x in range(GRID_SIZE + 1):
            px = x * CELL_SIZE
            pygame.draw.line(self.screen, GRID_COLOR, (px, HEADER_HEIGHT), (px, WINDOW_HEIGHT))
        for y in range(GRID_SIZE + 1):
            py = HEADER_HEIGHT + y * CELL_SIZE
            pygame.draw.line(self.screen, GRID_COLOR, (0, py), (WINDOW_WIDTH, py))

    def draw_snake(self):
        for (x, y) in self.snake.get_positions():
            rect = pygame.Rect(x * CELL_SIZE, HEADER_HEIGHT + y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(self.screen, SNAKE_COLOR, rect)

    def draw_food(self):
        pos = self.food.get_position()
        if pos is None:
            return
        x, y = pos
        rect = pygame.Rect(x * CELL_SIZE, HEADER_HEIGHT + y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(self.screen, FOOD_COLOR, rect)

    def draw_ui(self):
        # Score at the top
        score_surf = self.font.render(f"Score: {self.score}", True, TEXT_COLOR)
        self.screen.blit(score_surf, (10, 10))
        # Controls below score
        controls = "Arrow keys: Move   R: Restart   Esc: Quit"
        ctrl_surf = self.font.render(controls, True, TEXT_COLOR)
        self.screen.blit(ctrl_surf, (10, 40))

    def draw_game_over(self):
        if not self.game_over:
            return
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT - HEADER_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, HEADER_HEIGHT))
        text = self.large_font.render("GAME OVER", True, GAME_OVER_COLOR)
        sub = self.font.render(f"Final Score: {self.score}", True, TEXT_COLOR)
        tx = (WINDOW_WIDTH - text.get_width()) // 2
        ty = HEADER_HEIGHT + (WINDOW_HEIGHT - HEADER_HEIGHT) // 2 - text.get_height()
        self.screen.blit(text, (tx, ty))
        sx = (WINDOW_WIDTH - sub.get_width()) // 2
        self.screen.blit(sub, (sx, ty + text.get_height() + 10))

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event.key)

            # update game logic
            self.update()

            # render
            self.draw_grid()
            self.draw_food()
            self.draw_snake()
            self.draw_ui()
            self.draw_game_over()

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()


def main():
    game = Game()
    game.run()


if __name__ == '__main__':
    main()
