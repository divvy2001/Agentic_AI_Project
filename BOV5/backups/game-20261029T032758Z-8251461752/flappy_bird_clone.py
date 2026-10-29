import sys
import os
from pathlib import Path
import random
import pygame

# Ensure package imports work both ways
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Window and gameplay constants (from Plan)
WIDTH = 800
HEIGHT = 600
FPS = 60

BIRD_X = 100  # fixed horizontal position (near left)
BIRD_SIZE = (32, 32)
PIPE_SPEED = 200  # pixels per second
PIPE_SPAWN_INTERVAL_MS = 1500
GAP_SIZE = 150
GAP_MARGIN = 50

GRAVITY = 900.0  # px/s^2
JUMP_VELOCITY = -320.0  # px/s (instant set on flap)

# Colors
SKY_BLUE = (135, 206, 235)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def load_image(name):
    assets_dir = Path(__file__).resolve().parent / 'assets'
    path = assets_dir / name
    try:
        img = pygame.image.load(str(path)).convert_alpha()
    except Exception:
        raise
    return img


class FlappyBirdGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Flappy Bird Clone")
        self.clock = pygame.time.Clock()

        # Load assets
        self.bird_img = load_image('bird.png')
        # Ensure bird image is expected size
        self.bird_img = pygame.transform.scale(self.bird_img, BIRD_SIZE)

        self.pipe_img = load_image('pipe_segment.png')
        # We'll scale pipe segments vertically per-pipe; keep original width for reference
        self.pipe_width = self.pipe_img.get_width()

        # Font
        self.font = pygame.font.Font(None, 36)

        # Game state
        self.reset_game()

    def reset_game(self):
        # bird state
        self.bird = {
            'x': float(BIRD_X),
            'y': float(HEIGHT // 2) - BIRD_SIZE[1] / 2,
            'vel_y': 0.0,
            'width': BIRD_SIZE[0],
            'height': BIRD_SIZE[1],
            'image': self.bird_img,
        }
        # pipes: list of dicts {x: float, gap_y: float, passed: bool}
        self.pipes = []
        self.score = 0
        self.game_over = False
        self.last_spawn_time = pygame.time.get_ticks()
        self.running = True

    def spawn_pipe(self):
        half_gap = GAP_SIZE / 2
        min_y = GAP_MARGIN + half_gap
        max_y = HEIGHT - GAP_MARGIN - half_gap
        gap_y = random.uniform(min_y, max_y)
        pipe = {
            'x': float(WIDTH),
            'gap_y': gap_y,
            'passed': False,
        }
        self.pipes.append(pipe)

    def check_collisions(self):
        # Bird rect
        brect = pygame.Rect(int(self.bird['x']), int(self.bird['y']), self.bird['width'], self.bird['height'])

        # Check top/bottom bounds
        if self.bird['y'] < 0 or (self.bird['y'] + self.bird['height']) > HEIGHT:
            if not self.game_over:
                print("GAME OVER", flush=True)
                self.game_over = True
            return True

        # Check against pipes
        for p in self.pipes:
            x = int(p['x'])
            half_gap = GAP_SIZE / 2
            top_h = int(p['gap_y'] - half_gap)
            bottom_y = int(p['gap_y'] + half_gap)
            top_rect = pygame.Rect(x, 0, self.pipe_width, top_h)
            bottom_rect = pygame.Rect(x, bottom_y, self.pipe_width, HEIGHT - bottom_y)
            if brect.colliderect(top_rect) or brect.colliderect(bottom_rect):
                if not self.game_over:
                    print("GAME OVER", flush=True)
                    self.game_over = True
                return True
        return False

    def update(self, dt):
        # dt in seconds
        if not self.game_over:
            # Bird physics
            self.bird['vel_y'] += GRAVITY * dt
            self.bird['y'] += self.bird['vel_y'] * dt

            # Move pipes
            for p in self.pipes:
                p['x'] -= PIPE_SPEED * dt

            # Spawn new pipes at interval
            now = pygame.time.get_ticks()
            if now - self.last_spawn_time >= PIPE_SPAWN_INTERVAL_MS:
                self.spawn_pipe()
                self.last_spawn_time = now

            # Remove off-screen pipes
            self.pipes = [p for p in self.pipes if p['x'] + self.pipe_width > 0]

            # Check scoring: when bird passes pipe (bird.x > pipe.x + width) and not yet passed
            for p in self.pipes:
                if not p['passed'] and (self.bird['x'] > p['x'] + self.pipe_width):
                    p['passed'] = True
                    self.score += 1
                    # Print event for score change per Playbook
                    print(f"[EVENT] SCORE:{self.score}", flush=True)

            # Check collisions (this may set game_over)
            self.check_collisions()

    def draw(self):
        # Background
        self.screen.fill(SKY_BLUE)

        # Draw pipes
        for p in self.pipes:
            x = int(p['x'])
            half_gap = GAP_SIZE / 2
            top_h = int(p['gap_y'] - half_gap)
            bottom_h = int(HEIGHT - (p['gap_y'] + half_gap))

            # Draw top pipe (flip vertically)
            if top_h > 0:
                top_img = pygame.transform.scale(self.pipe_img, (self.pipe_width, top_h))
                top_img = pygame.transform.flip(top_img, False, True)
                self.screen.blit(top_img, (x, 0))

            # Draw bottom pipe
            if bottom_h > 0:
                bottom_img = pygame.transform.scale(self.pipe_img, (self.pipe_width, bottom_h))
                self.screen.blit(bottom_img, (x, int(p['gap_y'] + half_gap)))

        # Draw bird
        self.screen.blit(self.bird['image'], (int(self.bird['x']), int(self.bird['y'])))

        # Draw score top-left
        score_surf = self.font.render(str(self.score), True, BLACK)
        self.screen.blit(score_surf, (10, 10))

        # If game over, overlay text
        if self.game_over:
            over_surf = self.font.render("GAME OVER", True, BLACK)
            rect = over_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20))
            self.screen.blit(over_surf, rect)

            final_surf = self.font.render(f"Final Score: {self.score}", True, BLACK)
            rect2 = final_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20))
            self.screen.blit(final_surf, rect2)

        pygame.display.flip()

    def run(self):
        while self.running:
            dt_ms = self.clock.tick(FPS)
            dt = dt_ms / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("QUIT", flush=True)
                    self.running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        # Flap: set vertical velocity instantly
                        self.bird['vel_y'] = JUMP_VELOCITY
                        print("FLAP", flush=True)
                    elif event.key == pygame.K_r:
                        # Restart
                        print("RESTART", flush=True)
                        self.reset_game()
                    elif event.key == pygame.K_ESCAPE:
                        print("QUIT", flush=True)
                        self.running = False

            # Update only if running; reset_game will set game_over False
            self.update(dt)
            self.draw()

        pygame.quit()


def main():
    game = FlappyBirdGame()
    game.run()


if __name__ == '__main__':
    main()
