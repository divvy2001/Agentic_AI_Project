# Game constants for Snake
GRID_SIZE = 20
RESOLUTION_WIDTH = 600
RESOLUTION_HEIGHT = 680
FPS = 10
# Derive cell size and UI height so grid fits in width and leaves space for UI
CELL_SIZE = RESOLUTION_WIDTH // GRID_SIZE  # 30
GRID_PIXEL_SIZE = CELL_SIZE * GRID_SIZE  # 600
UI_HEIGHT = RESOLUTION_HEIGHT - GRID_PIXEL_SIZE  # 80

# Colors (R,G,B)
BG_COLOR = (30, 30, 30)
UI_BG_COLOR = (20, 20, 20)
GRID_COLOR = (50, 50, 50)
SNAKE_COLOR = (0, 200, 0)
FOOD_COLOR = (200, 0, 0)
TEXT_COLOR = (240, 240, 240)

# Controls display
CONTROLS_TEXT = "Arrows: Move   R: Restart   Esc: Quit"
