import sys
import os
from pathlib import Path
import random
import pygame

# Ensure module works when run as a script or as a module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

LIGHT_BLUE = (173, 216, 230)
TEXT_COLOR = (10, 10, 10)

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Kitty Catch')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 32)
        self.large_font = pygame.font.Font(None, 72)

        # Load assets
        assets_dir = Path(__file__).resolve().parent / 'assets'
        cat_path = assets_dir / 'cartoon_cat.png'
        fish_path = assets_dir / 'fish.png'
        try:
            self.cat_img = pygame.image.load(str(cat_path)).convert_alpha()
        except Exception:
            # Fallback: simple rectangle surface if asset missing (should not happen per Plan)
            self.cat_img = pygame.Surface((64, 64), pygame.SRCALPHA)
            pygame.draw.ellipse(self.cat_img, (200, 150, 150), self.cat_img.get_rect())
        try:
            self.fish_img = pygame.image.load(str(fish_path)).convert_alpha()
        except Exception:
            self.fish_img = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.ellipse(self.fish_img, (150, 200, 150), self.fish_img.get_rect())

        # Sizes
        self.cat_width = self.cat_img.get_width()
        self.cat_height = self.cat_img.get_height()
        self.fish_width = self.fish_img.get_width()
        self.fish_height = self.fish_img.get_height()

        # Game state
        self.score = 0
        self.missed = 0
        self.game_over = False
        self.cat_speed = 400  # pixels per second when moving

        # Place cat at bottom center
        cat_x = (SCREEN_WIDTH - self.cat_width) // 2
        cat_y = SCREEN_HEIGHT - self.cat_height - 10
        self.cat_rect = pygame.Rect(cat_x, cat_y, self.cat_width, self.cat_height)

        # Fish list: each fish is {'rect': pygame.Rect, 'speed': float}
        self.fishes = []
        self.spawn_timer = 0.0
        self.spawn_interval = 1.0  # seconds between spawns

        # Input tracking for printing on keydown only
        self.left_held = False
        self.right_held = False

        # Print initial state (not required but helpful)

    def reset(self):
        self.score = 0
        self.missed = 0
        self.game_over = False
        self.fishes.clear()
        self.spawn_timer = 0.0
        # Reset cat position to bottom center
        self.cat_rect.x = (SCREEN_WIDTH - self.cat_width) // 2
        self.cat_rect.y = SCREEN_HEIGHT - self.cat_height - 10
        print('RESTART', flush=True)

    def spawn_fish(self):
        x = random.randint(0, SCREEN_WIDTH - self.fish_width)
        y = -self.fish_height
        rect = pygame.Rect(x, y, self.fish_width, self.fish_height)
        speed = random.uniform(150, 260)  # pixels per second
        self.fishes.append({'rect': rect, 'speed': speed})

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            print('QUIT', flush=True)
            pygame.quit()
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                print('QUIT', flush=True)
                pygame.quit()
                sys.exit()
            if event.key == pygame.K_r:
                self.reset()
            if event.key == pygame.K_LEFT:
                # Mark held; print MOVE LEFT only on keydown
                self.left_held = True
                # Move a small immediate step so "pressing LEFT moves the cat" is satisfied
                old_x = self.cat_rect.x
                self.cat_rect.x -= int(self.cat_speed * (1.0 / FPS))
                # clamp
                if self.cat_rect.x < 0:
                    self.cat_rect.x = 0
                if self.cat_rect.x != old_x:
                    print('MOVE LEFT', flush=True)
            if event.key == pygame.K_RIGHT:
                self.right_held = True
                old_x = self.cat_rect.x
                self.cat_rect.x += int(self.cat_speed * (1.0 / FPS))
                if self.cat_rect.x > SCREEN_WIDTH - self.cat_width:
                    self.cat_rect.x = SCREEN_WIDTH - self.cat_width
                if self.cat_rect.x != old_x:
                    print('MOVE RIGHT', flush=True)
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_LEFT:
                self.left_held = False
            if event.key == pygame.K_RIGHT:
                self.right_held = False

    def update(self, dt):
        # Movement from held keys
        if not self.game_over:
            moved = False
            if self.left_held:
                old_x = self.cat_rect.x
                self.cat_rect.x -= int(self.cat_speed * dt)
                if self.cat_rect.x < 0:
                    self.cat_rect.x = 0
                if self.cat_rect.x != old_x:
                    moved = True
                # Do not print repeatedly while held (print already on KEYDOWN)
            if self.right_held:
                old_x = self.cat_rect.x
                self.cat_rect.x += int(self.cat_speed * dt)
                if self.cat_rect.x > SCREEN_WIDTH - self.cat_width:
                    self.cat_rect.x = SCREEN_WIDTH - self.cat_width
                if self.cat_rect.x != old_x:
                    moved = True

            # Spawn fishes
            self.spawn_timer += dt
            if self.spawn_timer >= self.spawn_interval:
                self.spawn_timer -= self.spawn_interval
                self.spawn_fish()

            # Update fishes
            for fish in list(self.fishes):
                fish_rect = fish['rect']
                fish_rect.y += int(fish['speed'] * dt)
                # Check collision with cat
                if fish_rect.colliderect(self.cat_rect):
                    self.fishes.remove(fish)
                    self.score += 1
                    print(f'SCORE:{self.score}', flush=True)
                # Check if missed bottom
                elif fish_rect.top > SCREEN_HEIGHT:
                    self.fishes.remove(fish)
                    self.missed += 1
                    # If missed reaches 3, game over
                    if self.missed >= 3:
                        self.game_over = True
                        print('GAME OVER', flush=True)
                        # Freeze fishes by not updating them further (we've removed the one that caused end)
        else:
            # game_over: do not spawn or move fishes
            pass

    def draw(self):
        self.screen.fill(LIGHT_BLUE)
        # Draw cat
        self.screen.blit(self.cat_img, (self.cat_rect.x, self.cat_rect.y))
        # Draw fishes
        for fish in self.fishes:
            r = fish['rect']
            self.screen.blit(self.fish_img, (r.x, r.y))
        # Draw score and missed top-left
        text = f'Score: {self.score}  Missed: {self.missed}'
        surf = self.font.render(text, True, TEXT_COLOR)
        self.screen.blit(surf, (10, 10))

        # If game over, draw overlay
        if self.game_over:
            go_surf = self.large_font.render('GAME OVER', True, (200, 10, 10))
            go_rect = go_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30))
            self.screen.blit(go_surf, go_rect)
            score_surf = self.font.render(f'Final Score: {self.score}', True, TEXT_COLOR)
            score_rect = score_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30))
            self.screen.blit(score_surf, score_rect)

    def run(self):
        # Main loop
        while True:
            dt = self.clock.tick(FPS) / 1000.0  # seconds
            for event in pygame.event.get():
                self.handle_event(event)
            # Update
            self.update(dt)
            # Draw
            self.draw()
            pygame.display.flip()


if __name__ == '__main__':
    Game().run()
