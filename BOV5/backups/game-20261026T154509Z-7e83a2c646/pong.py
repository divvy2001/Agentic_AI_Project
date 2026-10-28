import sys
import os
import random
import pygame
from pathlib import Path

# Ensure package imports work when executed as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class Game:
    """Pong game implementing the Planner contract.

    State owned here:
      - left_rect/right_rect: pygame.Rect for paddles
      - ball_rect: pygame.Rect for ball
      - ball_vel: [float, float]
      - left_score/right_score: int
      - game_over: bool
    """

    WIDTH = 800
    HEIGHT = 600
    FPS = 60

    PADDLE_WIDTH = 10
    PADDLE_HEIGHT = 100
    BALL_SIZE = 12

    PADDLE_SPEED = 400.0  # pixels per second
    BALL_SPEED = 300.0

    WIN_SCORE = 5

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Pong")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font = pygame.font.Font(None, 36)
        self.big_font = pygame.font.Font(None, 72)

        # Paddles
        left_x = 30
        right_x = self.WIDTH - 30 - self.PADDLE_WIDTH
        mid_y = (self.HEIGHT - self.PADDLE_HEIGHT) // 2
        self.left_rect = pygame.Rect(left_x, mid_y, self.PADDLE_WIDTH, self.PADDLE_HEIGHT)
        self.right_rect = pygame.Rect(right_x, mid_y, self.PADDLE_WIDTH, self.PADDLE_HEIGHT)

        # Ball
        self.ball_rect = pygame.Rect(0, 0, self.BALL_SIZE, self.BALL_SIZE)

        # Scores and state
        self.left_score = 0
        self.right_score = 0
        self.game_over = False

        # Initialize ball in center
        self.reset_ball()

        # To support clean shutdown
        self.running = True

    def reset_ball(self):
        """Place ball in center and give it a diagonal velocity."""
        self.ball_rect.center = (self.WIDTH // 2, self.HEIGHT // 2)
        # Randomize initial direction but ensure it's diagonal-ish
        angle = random.choice([30, 45, 60])
        rad = angle * (3.14159265 / 180.0)
        dir_x = random.choice([-1, 1])
        dir_y = random.choice([-1, 1])
        self.ball_vel = [dir_x * self.BALL_SPEED * abs(math_cos(rad)), dir_y * self.BALL_SPEED * abs(math_sin(rad))]

    def reset_game(self):
        """Reset scores, paddles and ball to initial playable state."""
        self.left_score = 0
        self.right_score = 0
        # Reset paddles to center
        mid_y = (self.HEIGHT - self.PADDLE_HEIGHT) // 2
        self.left_rect.y = mid_y
        self.right_rect.y = mid_y
        self.game_over = False
        self.reset_ball()
        print("[EVENT] RESET")

    def handle_events(self):
        """Process events: Quit, Escape, R for reset."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_r:
                    # R resets the whole game (scores and positions)
                    self.reset_game()

    def update(self, dt):
        """Update game state. dt in seconds."""
        if self.game_over:
            return

        keys = pygame.key.get_pressed()
        # Left paddle: W / S
        if keys[pygame.K_w]:
            self.left_rect.y -= int(self.PADDLE_SPEED * dt)
        if keys[pygame.K_s]:
            self.left_rect.y += int(self.PADDLE_SPEED * dt)
        # Right paddle: Up / Down
        if keys[pygame.K_UP]:
            self.right_rect.y -= int(self.PADDLE_SPEED * dt)
        if keys[pygame.K_DOWN]:
            self.right_rect.y += int(self.PADDLE_SPEED * dt)

        # Clamp paddles to screen
        self.left_rect.y = max(0, min(self.HEIGHT - self.PADDLE_HEIGHT, self.left_rect.y))
        self.right_rect.y = max(0, min(self.HEIGHT - self.PADDLE_HEIGHT, self.right_rect.y))

        # Move ball
        self.ball_rect.x += int(self.ball_vel[0] * dt)
        self.ball_rect.y += int(self.ball_vel[1] * dt)

        # Collide with top/bottom
        if self.ball_rect.top <= 0:
            self.ball_rect.top = 0
            self.ball_vel[1] = -self.ball_vel[1]
        elif self.ball_rect.bottom >= self.HEIGHT:
            self.ball_rect.bottom = self.HEIGHT
            self.ball_vel[1] = -self.ball_vel[1]

        # Collide with paddles
        if self.ball_rect.colliderect(self.left_rect) and self.ball_vel[0] < 0:
            self.ball_rect.left = self.left_rect.right
            self.ball_vel[0] = -self.ball_vel[0]
            # tweak y velocity based on where it hit the paddle
            offset = (self.ball_rect.centery - self.left_rect.centery) / (self.PADDLE_HEIGHT / 2)
            self.ball_vel[1] += offset * 150
        elif self.ball_rect.colliderect(self.right_rect) and self.ball_vel[0] > 0:
            self.ball_rect.right = self.right_rect.left
            self.ball_vel[0] = -self.ball_vel[0]
            offset = (self.ball_rect.centery - self.right_rect.centery) / (self.PADDLE_HEIGHT / 2)
            self.ball_vel[1] += offset * 150

        # Score when ball passes left/right
        if self.ball_rect.right < 0:
            # right player scores
            self.right_score += 1
            print(f"[EVENT] SCORE: {self.left_score}-{self.right_score}")
            if self.right_score >= self.WIN_SCORE:
                self.game_over = True
                self.ball_vel = [0, 0]
                print("[EVENT] WIN: Right")
            self.reset_ball()
        elif self.ball_rect.left > self.WIDTH:
            # left player scores
            self.left_score += 1
            print(f"[EVENT] SCORE: {self.left_score}-{self.right_score}")
            if self.left_score >= self.WIN_SCORE:
                self.game_over = True
                self.ball_vel = [0, 0]
                print("[EVENT] WIN: Left")
            self.reset_ball()

    def draw(self):
        self.screen.fill((0, 0, 0))

        # Draw center line
        for y in range(0, self.HEIGHT, 20):
            pygame.draw.rect(self.screen, (200, 200, 200), (self.WIDTH // 2 - 1, y, 2, 10))

        # Draw paddles and ball
        pygame.draw.rect(self.screen, (255, 255, 255), self.left_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), self.right_rect)
        pygame.draw.ellipse(self.screen, (255, 255, 255), self.ball_rect)

        # Draw scores and controls at top
        score_surf = self.font.render(f"{self.left_score}    {self.right_score}", True, (255, 255, 255))
        score_rect = score_surf.get_rect(center=(self.WIDTH // 2, 20))
        self.screen.blit(score_surf, score_rect)

        controls = self.font.render("Left: W/S    Right: Up/Down    R: Reset    Esc: Quit", True, (200, 200, 200))
        controls_rect = controls.get_rect(center=(self.WIDTH // 2, 50))
        self.screen.blit(controls, controls_rect)

        # If game over, show winner
        if self.game_over:
            if self.left_score > self.right_score:
                text = "Player 1 Wins!"
            else:
                text = "Player 2 Wins!"
            win_surf = self.big_font.render(text, True, (255, 220, 0))
            win_rect = win_surf.get_rect(center=(self.WIDTH // 2, self.HEIGHT // 2))
            self.screen.blit(win_surf, win_rect)

        pygame.display.flip()

    def run(self):
        """Main loop"""
        while self.running:
            dt = self.clock.tick(self.FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()


# Math helpers using local definitions to avoid importing math module repeatedly
def math_cos(x):
    # Taylor isn't necessary; import math here to keep top-level imports minimal
    import math

    return math.cos(x)


def math_sin(x):
    import math

    return math.sin(x)


if __name__ == "__main__":
    Game().run()
