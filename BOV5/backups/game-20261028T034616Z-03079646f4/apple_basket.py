import sys
import os
from pathlib import Path
import random
import pygame

# Ensure package imports work when run as module or script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Game constants (from Plan)
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

APPLE_RADIUS = 12
APPLE_SPEED = 180.0  # pixels per second
SPAWN_INTERVAL = 0.9  # seconds between apples
BASKET_SPEED = 360.0  # pixels per second
MAX_MISSED = 3

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Apple Basket")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 32)
        self.large_font = pygame.font.Font(None, 72)

        # Load assets
        assets_dir = Path(__file__).resolve().parent / 'assets'
        basket_path = assets_dir / 'woven_basket.png'
        bg_path = assets_dir / 'orchard_background.png'

        # Load background and scale to window
        try:
            self.bg_image = pygame.image.load(str(bg_path)).convert()
            self.bg_image = pygame.transform.scale(self.bg_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except Exception:
            # If asset loading fails, fall back to a plain color background
            self.bg_image = None

        try:
            self.basket_image = pygame.image.load(str(basket_path)).convert_alpha()
        except Exception:
            # Fallback: draw a simple rectangle as basket
            self.basket_image = pygame.Surface((96, 64), pygame.SRCALPHA)
            pygame.draw.rect(self.basket_image, (139, 69, 19), self.basket_image.get_rect())

        # Ensure basket image size variables
        self.basket_width = self.basket_image.get_width()
        self.basket_height = self.basket_image.get_height()

        # World state
        self.reset()

    def reset(self):
        # Reinitialize all game state
        self.score = 0
        self.missed = 0
        self.apples = []  # list of dicts: {'x':float,'y':float,'r':int}
        # Basket position: top-left coordinate
        self.basket_x = (SCREEN_WIDTH - self.basket_width) / 2.0
        self.basket_y = SCREEN_HEIGHT - self.basket_height - 16
        self.move_dir = 0  # -1 left, 1 right, 0 none
        self.spawn_timer = 0.0
        self.game_over = False
        # Print RESTART as required
        print("RESTART", flush=True)

    def spawn_apple(self):
        x = random.uniform(APPLE_RADIUS, SCREEN_WIDTH - APPLE_RADIUS)
        y = -APPLE_RADIUS
        self.apples.append({'x': x, 'y': y, 'r': APPLE_RADIUS})

    def handle_event(self, event):
        # Key events and quit
        if event.type == pygame.QUIT:
            print("QUIT", flush=True)
            pygame.quit()
            sys.exit()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                print("QUIT", flush=True)
                pygame.quit()
                sys.exit()
            elif event.key == pygame.K_r:
                # Restart
                self.reset()
                # Reset prints RESTART inside reset()
            elif event.key == pygame.K_LEFT:
                self.move_dir = -1
                print("MOVE LEFT", flush=True)
            elif event.key == pygame.K_RIGHT:
                self.move_dir = 1
                print("MOVE RIGHT", flush=True)

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_LEFT:
                # If right is still held, continue moving right
                keys = pygame.key.get_pressed()
                if keys[pygame.K_RIGHT]:
                    self.move_dir = 1
                else:
                    self.move_dir = 0
            elif event.key == pygame.K_RIGHT:
                keys = pygame.key.get_pressed()
                if keys[pygame.K_LEFT]:
                    self.move_dir = -1
                else:
                    self.move_dir = 0

    def update(self, dt):
        # If game over, do not update apples or spawn new ones
        if self.game_over:
            return

        # Move basket
        if self.move_dir != 0:
            self.basket_x += self.move_dir * BASKET_SPEED * dt
            # Clamp to screen edges
            self.basket_x = max(0, min(self.basket_x, SCREEN_WIDTH - self.basket_width))

        # Spawn apples on timer
        self.spawn_timer += dt
        while self.spawn_timer >= SPAWN_INTERVAL:
            self.spawn_timer -= SPAWN_INTERVAL
            self.spawn_apple()

        # Update apples positions and check collisions/bottom
        new_apples = []
        basket_rect = pygame.Rect(int(self.basket_x), int(self.basket_y), self.basket_width, self.basket_height)
        for apple in self.apples:
            apple['y'] += APPLE_SPEED * dt
            # Check for catch: simple check if bottom point of apple is inside basket rect
            if basket_rect.collidepoint(apple['x'], apple['y'] + apple['r']):
                self.score += 1
                print(f"[EVENT] SCORE:{self.score}", flush=True)
                continue  # apple caught, do not keep
            # Check for missed
            if apple['y'] - apple['r'] > SCREEN_HEIGHT:
                self.missed += 1
                # Print missed event (not strictly required, but useful)
                print(f"[EVENT] MISSED:{self.missed}", flush=True)
                if self.missed >= MAX_MISSED:
                    # Game over
                    self.game_over = True
                    print("GAME OVER", flush=True)
                    print(f"[EVENT] GAME OVER", flush=True)
                    # Stop processing remaining apples (they freeze visually)
                    break
                continue
            new_apples.append(apple)

        self.apples = new_apples

    def draw(self):
        # Draw background
        if self.bg_image:
            self.screen.blit(self.bg_image, (0, 0))
        else:
            self.screen.fill((120, 200, 80))

        # Draw apples as red circles
        for apple in self.apples:
            pygame.draw.circle(self.screen, (220, 20, 60), (int(apple['x']), int(apple['y'])), apple['r'])

        # Draw basket
        self.screen.blit(self.basket_image, (int(self.basket_x), int(self.basket_y)))

        # Draw HUD: Score and Missed in top-left
        hud_surf = self.font.render(f"Score: {self.score}   Missed: {self.missed}", True, (255, 255, 255))
        self.screen.blit(hud_surf, (8, 8))

        # If game over, draw overlay text
        if self.game_over:
            go_surf = self.large_font.render("GAME OVER", True, (255, 10, 10))
            go_rect = go_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30))
            self.screen.blit(go_surf, go_rect)

            score_surf = self.font.render(f"Final Score: {self.score}", True, (255, 255, 255))
            score_rect = score_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30))
            self.screen.blit(score_surf, score_rect)

    def run(self):
        # Main loop
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                self.handle_event(event)

            # Update world
            self.update(dt)

            # Draw
            self.draw()
            pygame.display.flip()


if __name__ == '__main__':
    Game().run()
