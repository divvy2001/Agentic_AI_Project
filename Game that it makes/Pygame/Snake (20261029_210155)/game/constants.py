# Game constants for Snake
from typing import Tuple

GRID_SIZE = 20  # 20x20 grid
WIDTH = 600
HEIGHT = 680  # includes HUD
CELL_SIZE = WIDTH // GRID_SIZE  # 30 pixels
HUD_HEIGHT = HEIGHT - GRID_SIZE * CELL_SIZE  # top area for score and controls
FPS = 10

# Colors (R,G,B)
COLOR_BG = (40, 40, 40)
COLOR_GRID = (60, 60, 60)
COLOR_SNAKE = (0, 200, 0)
COLOR_FOOD = (200, 0, 0)
COLOR_HUD_TEXT = (230, 230, 230)
COLOR_GAME_OVER = (255, 50, 50)

# Directions as (dx, dy)
DIR_UP = (0, -1)
DIR_DOWN = (0, 1)
DIR_LEFT = (-1, 0)
DIR_RIGHT = (1, 0)

DIRECTIONS = {
    'UP': DIR_UP,
    'DOWN': DIR_DOWN,
    'LEFT': DIR_LEFT,
    'RIGHT': DIR_RIGHT,
}
