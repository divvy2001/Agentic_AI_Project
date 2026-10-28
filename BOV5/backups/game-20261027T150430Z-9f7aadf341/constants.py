import pygame

# Screen
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Colors
LIGHT_BG = (220, 220, 230)
WOOD_BROWN = (160, 110, 60)
HEALTH_BG = (80, 80, 80)
HEALTH_PLAYER = (50, 200, 50)
HEALTH_RIVAL = (50, 100, 200)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Physics
GRAVITY = 1200  # pixels per second^2
MOVE_SPEED = 200  # pixels per second
JUMP_SPEED = 500  # initial jump velocity (px/s)

# Fighter
FIGHTER_WIDTH = 64
FIGHTER_HEIGHT = 64
PUNCH_DURATION = 0.25  # seconds
PUNCH_COOLDOWN = 0.6  # seconds for player
AI_PUNCH_COOLDOWN = 1.0  # seconds for rival
PUNCH_RANGE = 40  # pixels in front of fighter
PUNCH_DAMAGE = 10
KNOCKBACK = 30  # pixels moved when hit
FLASH_TIME = 0.15  # seconds

# Floor
FLOOR_HEIGHT = 80  # height in pixels of floor area at bottom
FLOOR_Y = SCREEN_HEIGHT - FLOOR_HEIGHT

# Health
MAX_HEALTH = 100
HEALTH_BAR_WIDTH = 300
HEALTH_BAR_HEIGHT = 20
HEALTH_BAR_MARGIN = 20

# AI
AI_SPEED = 120  # pixels per second
AI_PUNCH_DISTANCE = 60  # distance to player to trigger punch
