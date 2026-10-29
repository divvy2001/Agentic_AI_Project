import sys
import os
from pathlib import Path
import random
import pygame

# Ensure module imports work when running as a package or as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Game constants (from Plan)
TITLE = "Flappy Bird Clone"
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Bird constants
BIRD_X = 100  # fixed horizontal position near left
BIRD_W = 32
BIRD_H = 32
GRAVITY = 800.0  # pixels per second^2
FLAP_VELOCITY = -300.0  # instantaneous vy when flapping (up is negative)

# Pipe constants
PIPE_WIDTH = 64
GAP_SIZE = 180
PIPE_SPEED = 200.0  # pixels per second
PIPE_INTERVAL = 1.5  # seconds between pipes

# Colors
SKY_BLUE = (135, 206, 235)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)

        # Load assets (relative to this file)
        assets_dir = Path(__file__).resolve().parent / 'assets'
        try:
            self.bird_img = pygame.image.load(str(assets_dir / 'bird.png')).convert_alpha()
        except Exception:
            # Fallback procedural bird (should not be needed when assets exist)
            self.bird_img = pygame.Surface((BIRD_W, BIRD_H), pygame.SRCALPHA)
            pygame.draw.ellipse(self.bird_img, (255, 220, 0), (0, 0, BIRD_W, BIRD_H))
        try:
            self.pipe_img = pygame.image.load(str(assets_dir / 'pipe_segment.png')).convert_alpha()
        except Exception:
            # Fallback procedural pipe
            self.pipe_img = pygame.Surface((PIPE_WIDTH, 300), pygame.SRCALPHA)
            self.pipe_img.fill((34, 177, 76))

        # Game state
        self.reset_game()

    def reset_game(self):
        # Bird state
        self.bird_x = BIRD_X
        self.bird_y = SCREEN_HEIGHT / 2 - BIRD_H / 2
        self.bird_vy = 0.0

        # Pipes: list of dicts {x: float, gap_y: int, passed: bool}
        self.pipes = []

        # Timing for spawning pipes
        self.time_since_last_pipe = 0.0

        # Score and game flags
        self.score = 0
        self.game_over = False
        self._printed_game_over = False

        # For consistent input handling
        self.running = True

    def spawn_pipe(self):
        # gap center between margins to avoid impossible gaps
        margin = 50 + GAP_SIZE / 2
        gap_y = random.uniform(margin, SCREEN_HEIGHT - margin)
        pipe = {'x': float(SCREEN_WIDTH), 'gap_y': gap_y, 'passed': False}
        self.pipes.append(pipe)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            print('QUIT', flush=True)
            self.running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                print('QUIT', flush=True)
                self.running = False
            elif event.key == pygame.K_SPACE:
                # Flap only if playing (not after game over)
                if not self.game_over:
                    self.bird_vy = FLAP_VELOCITY
                    print('FLAP', flush=True)
            elif event.key == pygame.K_r:
                # Restart
                self.reset_game()
                print('RESTART', flush=True)

    def update(self, dt):
        if self.game_over:
            # Freeze positions after game over
            return

        # Bird physics
        self.bird_vy += GRAVITY * dt
        self.bird_y += self.bird_vy * dt

        # Spawn pipes regularly
        self.time_since_last_pipe += dt
        if self.time_since_last_pipe >= PIPE_INTERVAL:
            self.spawn_pipe()
            self.time_since_last_pipe -= PIPE_INTERVAL

        # Update pipes
        for pipe in self.pipes:
            pipe['x'] -= PIPE_SPEED * dt

        # Remove pipes that are off-screen
        self.pipes = [p for p in self.pipes if p['x'] + PIPE_WIDTH > 0]

        # Collision detection and scoring
        bird_rect = pygame.Rect(int(self.bird_x), int(self.bird_y), BIRD_W, BIRD_H)

        for pipe in self.pipes:
            gap_top = pipe['gap_y'] - GAP_SIZE / 2
            gap_bottom = pipe['gap_y'] + GAP_SIZE / 2
            top_rect = pygame.Rect(int(pipe['x']), 0, PIPE_WIDTH, int(gap_top))
            bottom_rect = pygame.Rect(int(pipe['x']), int(gap_bottom), PIPE_WIDTH, int(SCREEN_HEIGHT - gap_bottom))

            # Collision
            if bird_rect.colliderect(top_rect) or bird_rect.colliderect(bottom_rect):
                self.game_over = True

            # Scoring: when bird passes pipe's x + width
            if not pipe['passed'] and (self.bird_x > pipe['x'] + PIPE_WIDTH):
                pipe['passed'] = True
                self.score += 1
                print(f'SCORE:{self.score}', flush=True)

        # Check top/bottom collisions (out of bounds)
        if self.bird_y < 0 or (self.bird_y + BIRD_H) > SCREEN_HEIGHT:
            self.game_over = True

        if self.game_over and not self._printed_game_over:
            print('GAME OVER', flush=True)
            self._printed_game_over = True

    def draw(self):
        # Background
        self.screen.fill(SKY_BLUE)

        # Draw pipes
        for pipe in self.pipes:
            x = int(pipe['x'])
            gap_y = pipe['gap_y']
            gap_top = int(gap_y - GAP_SIZE / 2)
            gap_bottom = int(gap_y + GAP_SIZE / 2)

            # Top pipe: we need to draw the pipe image scaled to gap_top height and flipped vertically
            if gap_top > 0:
                top_height = gap_top
                top_img = pygame.transform.scale(self.pipe_img, (PIPE_WIDTH, top_height))
                top_img = pygame.transform.flip(top_img, False, True)
                self.screen.blit(top_img, (x, 0))

            # Bottom pipe
            bottom_height = SCREEN_HEIGHT - gap_bottom
            if bottom_height > 0:
                bottom_img = pygame.transform.scale(self.pipe_img, (PIPE_WIDTH, bottom_height))
                self.screen.blit(bottom_img, (x, gap_bottom))

        # Draw bird
        self.screen.blit(self.bird_img, (int(self.bird_x), int(self.bird_y)))

        # Draw score in top-left corner
        score_surf = self.font.render(str(self.score), True, BLACK)
        self.screen.blit(score_surf, (10, 10))

        # If game over, draw GAME OVER and final score prominently
        if self.game_over:
            over_surf = self.font.render('GAME OVER', True, BLACK)
            over_rect = over_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
            self.screen.blit(over_surf, over_rect)

            final_surf = self.font.render(f'Final Score: {self.score}', True, BLACK)
            final_rect = final_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
            self.screen.blit(final_surf, final_rect)

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                self.handle_event(event)

            self.update(dt)
            self.draw()
            pygame.display.flip()

        pygame.quit()


def main():
    game = Game()
    game.run()


if __name__ == '__main__':
    main()
