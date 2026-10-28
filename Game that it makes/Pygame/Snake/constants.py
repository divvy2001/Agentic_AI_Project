import pygame

# Grid and window
GRID_SIZE = 20
CELL_SIZE = 30  # pixels per cell -> 20 * 30 = 600 play area
PLAY_WIDTH = GRID_SIZE * CELL_SIZE
TOP_MARGIN = 80
WIDTH = PLAY_WIDTH
HEIGHT = TOP_MARGIN + PLAY_WIDTH

# Timing
FPS = 10

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (40, 40, 40)
LIGHT_GRAY = (60, 60, 60)
SNAKE_COLOR = (0, 200, 0)
FOOD_COLOR = (200, 0, 0)
BG_COLOR = (10, 10, 10)

# Fonts (will be created in runtime using pygame.font.Font(None, size))
SCORE_FONT_SIZE = 28
CTRL_FONT_SIZE = 18
GAMEOVER_FONT_SIZE = 48

# Directions as vectors
DIR_UP = (0, -1)
DIR_DOWN = (0, 1)
DIR_LEFT = (-1, 0)
DIR_RIGHT = (1, 0)
