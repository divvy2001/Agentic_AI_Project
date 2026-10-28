import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
import random

# Game settings from the Plan
WIDTH = 800
HEIGHT = 600
FPS = 60

PLAYER_SIZE = 50
PLAYER_COLOR = (0, 0, 255)  # Blue
ENEMY_SIZE = 40
ENEMY_COLOR = (255, 0, 0)  # Red
BG_COLOR = (30, 30, 30)
TEXT_COLOR = (255, 255, 255)

PLAYER_SPEED = 400  # pixels per second
ENEMY_SPEED_MIN = 150
ENEMY_SPEED_MAX = 300
SPAWN_INTERVAL_MIN = 0.5
SPAWN_INTERVAL_MAX = 1.2

class BlockDodgeGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption('Block Dodge')  # Requirement 0
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)

        # Owned state
        self.player_rect = None  # pygame.Rect
        self.enemies = []  # list of dicts: {'rect':Rect, 'speed':float}
        self.score = 0
        self.spawn_timer = 0.0
        self.game_over = False

        self.restart_game()

    def restart_game(self, announce=True):
        # Reset all game state to initial values (Requirement 9)
        self.player_rect = pygame.Rect(
            (WIDTH - PLAYER_SIZE) // 2,
            HEIGHT - PLAYER_SIZE - 10,
            PLAYER_SIZE,
            PLAYER_SIZE,
        )
        self.enemies = []
        self.score = 0
        self.spawn_timer = random.uniform(SPAWN_INTERVAL_MIN, SPAWN_INTERVAL_MAX)
        self.game_over = False
        # Print restart event when requested (Requirement 12)
        if announce:
            print('RESTART', flush=True)

    def spawn_enemy(self):
        x = random.randint(0, WIDTH - ENEMY_SIZE)
        rect = pygame.Rect(x, -ENEMY_SIZE, ENEMY_SIZE, ENEMY_SIZE)
        speed = random.uniform(ENEMY_SPEED_MIN, ENEMY_SPEED_MAX)
        self.enemies.append({'rect': rect, 'speed': speed})

    def handle_event(self, event):
        # Handle key presses for controls and other events
        if event.type == pygame.QUIT:
            print('QUIT', flush=True)
            pygame.quit()
            sys.exit()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                print('QUIT', flush=True)
                pygame.quit()
                sys.exit()
            if event.key == pygame.K_r:
                # Restart even if in play
                self.restart_game(announce=True)
            if event.key == pygame.K_LEFT:
                print('MOVE LEFT', flush=True)
            if event.key == pygame.K_RIGHT:
                print('MOVE RIGHT', flush=True)

    def update(self, dt):
        # dt in seconds
        if not self.game_over:
            keys = pygame.key.get_pressed()
            moved = False
            if keys[pygame.K_LEFT]:
                self.player_rect.x -= int(PLAYER_SPEED * dt)
                moved = True
            if keys[pygame.K_RIGHT]:
                self.player_rect.x += int(PLAYER_SPEED * dt)
                moved = True

            # Clamp to screen edges (Requirement 3)
            if self.player_rect.left < 0:
                self.player_rect.left = 0
            if self.player_rect.right > WIDTH:
                self.player_rect.right = WIDTH

            # Spawn logic
            self.spawn_timer -= dt
            if self.spawn_timer <= 0.0:
                self.spawn_enemy()
                self.spawn_timer = random.uniform(SPAWN_INTERVAL_MIN, SPAWN_INTERVAL_MAX)

            # Move enemies
            for enemy in list(self.enemies):
                enemy['rect'].y += int(enemy['speed'] * dt)
                # Check collision
                if enemy['rect'].colliderect(self.player_rect):
                    # Game over
                    self.game_over = True
                    print('GAME OVER', flush=True)
                    # On game over, we stop movement/spawning (handled by guards)
                    break
                # Check if enemy reached bottom
                if enemy['rect'].top > HEIGHT:
                    # Enemy escaped; increase score (Requirement 5)
                    self.enemies.remove(enemy)
                    self.score += 1
                    print(f'SCORE:{self.score}', flush=True)

    def draw(self):
        self.screen.fill(BG_COLOR)

        # Draw player
        pygame.draw.rect(self.screen, PLAYER_COLOR, self.player_rect)

        # Draw enemies
        for enemy in self.enemies:
            pygame.draw.rect(self.screen, ENEMY_COLOR, enemy['rect'])

        # Draw score (Requirement 6)
        score_surf = self.font.render(str(self.score), True, TEXT_COLOR)
        self.screen.blit(score_surf, (10, 10))

        # If game over, draw GAME OVER and final score and freeze (Requirement 7)
        if self.game_over:
            over_surf = self.font.render('GAME OVER', True, TEXT_COLOR)
            over_rect = over_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20))
            self.screen.blit(over_surf, over_rect)

            final_surf = self.font.render(f'Final Score: {self.score}', True, TEXT_COLOR)
            final_rect = final_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20))
            self.screen.blit(final_surf, final_rect)

        pygame.display.flip()

    def run(self):
        # Main game loop
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                self.handle_event(event)

            self.update(dt)
            self.draw()


def main():
    game = BlockDodgeGame()
    game.run()


if __name__ == '__main__':
    main()
