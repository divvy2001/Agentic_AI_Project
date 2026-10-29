import sys
import os
from pathlib import Path
import random
import pygame

# Ensure running as module or script works
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- Constants / configuration ---
WIDTH, HEIGHT = 800, 600
FPS = 60
TITLE = "Flappy Bird Clone"

BIRD_X = 100  # fixed horizontal position (left side)
BIRD_START_Y = HEIGHT // 2
BIRD_WIDTH = 32
BIRD_HEIGHT = 32
GRAVITY = 900.0  # pixels per second^2
FLAP_VELOCITY = -300.0  # instant upward velocity (pixels/sec)

PIPE_WIDTH = 64
GAP_SIZE = 150
PIPE_SPEED = 200.0  # pixels per second
PIPE_SPAWN_INTERVAL = 1.5  # seconds

SKY_BLUE = (135, 206, 235)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

ASSETS_DIR = Path(__file__).resolve().parent / 'assets'

# --- Game state (module-level ownership) ---
# Bird
bird_x = BIRD_X
bird_y = float(BIRD_START_Y)
bird_vy = 0.0

# Pipes: list of dicts with keys: x: float, gap_y: int, scored: bool
pipes = []

# Timers and score
time_since_last_pipe = 0.0
score = 0

# Game control flags
running = True
game_over = False

# Assets (loaded in init)
bird_img = None
pipe_img = None
font = None

# --- Helper functions / interfaces ---

def load_assets():
    global bird_img, pipe_img, font
    bird_path = ASSETS_DIR / 'bird.png'
    pipe_path = ASSETS_DIR / 'pipe_segment.png'
    # Load images; allow exceptions to propagate if missing (Planner guaranteed assets)
    bird_img = pygame.image.load(str(bird_path)).convert_alpha()
    pipe_img = pygame.image.load(str(pipe_path)).convert_alpha()
    # Use default font
    font = pygame.font.Font(None, 36)


def flap():
    global bird_vy
    bird_vy = FLAP_VELOCITY
    print('FLAP', flush=True)


def spawn_pipe():
    # gap_y is the top coordinate of the gap
    min_gap_y = 50
    max_gap_y = HEIGHT - 50 - GAP_SIZE
    gap_y = random.randint(min_gap_y, max_gap_y)
    pipe = {'x': float(WIDTH), 'gap_y': gap_y, 'scored': False}
    pipes.append(pipe)


def reset_game(suppress_print: bool = False):
    global bird_y, bird_vy, pipes, score, game_over, time_since_last_pipe
    bird_y = float(BIRD_START_Y)
    bird_vy = 0.0
    pipes = []
    score = 0
    game_over = False
    time_since_last_pipe = 0.0
    if not suppress_print:
        print('RESTART', flush=True)


def end_game():
    global game_over
    if not game_over:
        game_over = True
        print('GAME OVER', flush=True)


def update_bird(dt):
    global bird_y, bird_vy
    # integrate velocity
    bird_vy += GRAVITY * dt
    bird_y += bird_vy * dt


def update_pipes(dt):
    global pipes, score
    for pipe in pipes:
        pipe['x'] -= PIPE_SPEED * dt
    # remove pipes fully off-screen
    pipes = [p for p in pipes if p['x'] + PIPE_WIDTH > -50]

    # scoring: if pipe has passed the bird_x and not scored
    for pipe in pipes:
        if not pipe['scored'] and pipe['x'] + PIPE_WIDTH < bird_x:
            pipe['scored'] = True
            increment_score()


def increment_score():
    global score
    score += 1
    print(f'[EVENT] SCORE:{score}', flush=True)


def check_collisions():
    # bird rect
    bird_rect = pygame.Rect(int(bird_x), int(bird_y), BIRD_WIDTH, BIRD_HEIGHT)
    # out of bounds
    if bird_rect.top < 0 or bird_rect.bottom > HEIGHT:
        end_game()
        return

    # pipe collisions
    for pipe in pipes:
        px = int(pipe['x'])
        gap_y = pipe['gap_y']
        top_rect = pygame.Rect(px, 0, PIPE_WIDTH, gap_y)
        bottom_rect = pygame.Rect(px, gap_y + GAP_SIZE, PIPE_WIDTH, HEIGHT - (gap_y + GAP_SIZE))
        if bird_rect.colliderect(top_rect) or bird_rect.colliderect(bottom_rect):
            end_game()
            return


def draw(screen):
    # background
    screen.fill(SKY_BLUE)

    # draw pipes
    for pipe in pipes:
        px = int(pipe['x'])
        gap_y = pipe['gap_y']
        # top pipe
        top_h = gap_y
        if top_h > 0:
            top_img = pygame.transform.scale(pipe_img, (PIPE_WIDTH, max(1, top_h)))
            screen.blit(top_img, (px, 0))
        # bottom pipe
        bottom_h = HEIGHT - (gap_y + GAP_SIZE)
        if bottom_h > 0:
            bottom_img = pygame.transform.scale(pipe_img, (PIPE_WIDTH, max(1, bottom_h)))
            screen.blit(bottom_img, (px, gap_y + GAP_SIZE))

    # draw bird
    bird_draw_x = int(bird_x)
    bird_draw_y = int(bird_y)
    screen.blit(bird_img, (bird_draw_x, bird_draw_y))

    # draw score (top-left)
    score_surf = font.render(str(score), True, BLACK)
    screen.blit(score_surf, (10, 10))

    # game over text
    if game_over:
        go_surf = font.render('GAME OVER', True, BLACK)
        go_rect = go_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20))
        screen.blit(go_surf, go_rect)
        final_surf = font.render(f'Final Score: {score}', True, BLACK)
        final_rect = final_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20))
        screen.blit(final_surf, final_rect)


def main():
    global running, time_since_last_pipe
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()

    load_assets()
    reset_game(suppress_print=True)  # initialize state without printing RESTART

    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                print('QUIT', flush=True)
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    print('QUIT', flush=True)
                    running = False
                elif event.key == pygame.K_SPACE:
                    if not game_over:
                        flap()
                elif event.key == pygame.K_r:
                    reset_game()

        # update game only when not game over
        if not game_over:
            update_bird(dt)
            time_since_last_pipe += dt
            if time_since_last_pipe >= PIPE_SPAWN_INTERVAL:
                spawn_pipe()
                time_since_last_pipe -= PIPE_SPAWN_INTERVAL
            update_pipes(dt)
            check_collisions()

        # draw everything
        draw(screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == '__main__':
    main()
