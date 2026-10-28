import sys
import os
from pathlib import Path
import random
import pygame

# Ensure package imports work when run as a module or script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Game constants (from Plan)
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
WINDOW_TITLE = "Kitty Catch"

CAT_ASSET = Path(__file__).resolve().parent / "assets" / "cartoon_cat.png"
FISH_ASSET = Path(__file__).resolve().parent / "assets" / "fish.png"

# Gameplay constants
CAT_SPEED = 350  # pixels per second
FISH_MIN_SPEED = 120
FISH_MAX_SPEED = 260
SPAWN_INTERVAL = 0.8  # seconds
MAX_MISSED = 3


def load_image(path: Path) -> pygame.Surface:
    """Load an image from the assets folder and return a Surface with alpha.
    If loading fails, create a placeholder surface.
    """
    try:
        image = pygame.image.load(str(path)).convert_alpha()
        return image
    except Exception:
        # Fallback placeholder (should not be used: Plan supplies assets)
        surf = pygame.Surface((32, 32), pygame.SRCALPHA)
        surf.fill((255, 0, 255, 128))
        return surf


class KittyCatchGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 30)

        # Load assets
        self.cat_image = load_image(CAT_ASSET)
        self.fish_image = load_image(FISH_ASSET)

        # State owned by this class
        self.score = 0
        self.missed = 0
        self.game_over = False
        self.spawn_timer = 0.0
        self.fishes = []  # list of dicts {'rect': pygame.Rect, 'speed': float}

        # Cat setup: place at bottom center
        cat_w, cat_h = self.cat_image.get_size()
        self.cat_rect = pygame.Rect(0, 0, cat_w, cat_h)
        self.reset_cat_position()

        # Input flags
        self.move_left = False
        self.move_right = False

        # Control whether the main loop is running
        self.running = True

    def reset_cat_position(self):
        self.cat_rect.centerx = SCREEN_WIDTH // 2
        self.cat_rect.bottom = SCREEN_HEIGHT - 10

    def reset_game(self):
        self.score = 0
        self.missed = 0
        self.game_over = False
        self.spawn_timer = 0.0
        self.fishes.clear()
        self.reset_cat_position()

    def spawn_fish(self):
        fish_w, fish_h = self.fish_image.get_size()
        x = random.randint(0, SCREEN_WIDTH - fish_w)
        rect = pygame.Rect(x, -fish_h, fish_w, fish_h)
        speed = random.uniform(FISH_MIN_SPEED, FISH_MAX_SPEED)
        self.fishes.append({"rect": rect, "speed": speed})

    def handle_event(self, event: pygame.event.EventType):
        if event.type == pygame.QUIT:
            print("QUIT", flush=True)
            self.running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                print("MOVE LEFT", flush=True)
                self.move_left = True
            elif event.key == pygame.K_RIGHT:
                print("MOVE RIGHT", flush=True)
                self.move_right = True
            elif event.key == pygame.K_r:
                print("RESTART", flush=True)
                self.reset_game()
            elif event.key == pygame.K_ESCAPE:
                print("QUIT", flush=True)
                self.running = False

        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_LEFT:
                self.move_left = False
            elif event.key == pygame.K_RIGHT:
                self.move_right = False

    def update(self, dt: float):
        # If not game over, update spawn timer and fish positions
        if not self.game_over:
            self.spawn_timer += dt
            if self.spawn_timer >= SPAWN_INTERVAL:
                self.spawn_timer -= SPAWN_INTERVAL
                self.spawn_fish()

            # Update fish positions
            for fish in list(self.fishes):
                fish['rect'].y += int(fish['speed'] * dt)
                # Check collision with cat
                if fish['rect'].colliderect(self.cat_rect):
                    self.fishes.remove(fish)
                    self.score += 1
                    print(f"[EVENT] SCORE:{self.score}", flush=True)
                    continue
                # Check if fish passed bottom
                if fish['rect'].top > SCREEN_HEIGHT:
                    self.fishes.remove(fish)
                    self.missed += 1
                    if self.missed >= MAX_MISSED:
                        self.game_over = True
                        print("GAME OVER", flush=True)

        # Update cat movement (movement allowed both during play; when game_over we still allow no movement?)
        # Plan: when GAME OVER, fish freeze and no new fish spawn. Cat movement may still respond, but that's OK.
        dx = 0
        if self.move_left:
            dx -= CAT_SPEED * dt
        if self.move_right:
            dx += CAT_SPEED * dt
        if dx != 0:
            new_x = self.cat_rect.x + int(dx)
            # Clamp to screen edges
            new_x = max(0, min(new_x, SCREEN_WIDTH - self.cat_rect.width))
            self.cat_rect.x = new_x

    def draw(self):
        self.screen.fill((135, 206, 235))  # sky-blue background

        # Draw cat
        self.screen.blit(self.cat_image, self.cat_rect.topleft)

        # Draw fishes
        for fish in self.fishes:
            self.screen.blit(self.fish_image, fish['rect'].topleft)

        # HUD: Score and Missed in top-left corner
        score_surf = self.font.render(f"Score: {self.score}", True, (0, 0, 0))
        missed_surf = self.font.render(f"Missed: {self.missed}", True, (0, 0, 0))
        self.screen.blit(score_surf, (10, 10))
        self.screen.blit(missed_surf, (10, 40))

        # Game over overlay
        if self.game_over:
            go_surf = self.font.render("GAME OVER", True, (255, 0, 0))
            final_surf = self.font.render(f"Final Score: {self.score}", True, (0, 0, 0))
            go_rect = go_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
            final_rect = final_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
            self.screen.blit(go_surf, go_rect.topleft)
            self.screen.blit(final_surf, final_rect.topleft)

        pygame.display.flip()

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                self.handle_event(event)

            self.update(dt)
            self.draw()

        pygame.quit()


def main():
    game = KittyCatchGame()
    game.run()


if __name__ == "__main__":
    main()
