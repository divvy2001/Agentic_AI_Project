import sys
import os
import random
import pygame

# Ensure module imports work when running as a module or script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Game constants matching the Plan
WIDTH = 800
HEIGHT = 600
FPS = 60

PADDLE_WIDTH = 10
PADDLE_HEIGHT = 100
PADDLE_SPEED = 400  # pixels per second
BALL_SIZE = 12
BALL_SPEED = 300  # base speed in pixels per second
WIN_SCORE = 5

FONT_SIZE = 32
SMALL_FONT_SIZE = 20

class Game:
    """Encapsulates all game state and behavior.

    Public methods:
      - reset() -> None
      - serve(direction: int|None) -> None  # direction: -1 left, 1 right, None random
      - handle_events() -> bool  # returns False to quit
      - update(dt: float) -> None
      - draw(screen) -> None
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # paddles as pygame.Rect
        pad_x_offset = 20
        self.left_paddle = pygame.Rect(pad_x_offset, (height - PADDLE_HEIGHT)//2, PADDLE_WIDTH, PADDLE_HEIGHT)
        self.right_paddle = pygame.Rect(width - pad_x_offset - PADDLE_WIDTH, (height - PADDLE_HEIGHT)//2, PADDLE_WIDTH, PADDLE_HEIGHT)
        self.ball = pygame.Rect((width - BALL_SIZE)//2, (height - BALL_SIZE)//2, BALL_SIZE, BALL_SIZE)
        # velocities
        self.ball_vx = 0.0
        self.ball_vy = 0.0
        # scores
        self.score1 = 0
        self.score2 = 0
        # game state
        self.game_over = False
        self.winner = None  # 1 or 2

        # fonts (initialized after pygame.init typically)
        self.font = pygame.font.Font(None, FONT_SIZE)
        self.small_font = pygame.font.Font(None, SMALL_FONT_SIZE)

        # start play
        self.reset()

    def reset(self) -> None:
        """Reset scores, positions, velocities and unfreeze the game.
        As required: pressing R resets both scores to 0, places the ball in the center, and unfreezes the game.
        """
        self.score1 = 0
        self.score2 = 0
        self.game_over = False
        self.winner = None
        # reset positions
        self.left_paddle.y = (self.height - PADDLE_HEIGHT)//2
        self.right_paddle.y = (self.height - PADDLE_HEIGHT)//2
        self.ball.x = (self.width - BALL_SIZE)//2
        self.ball.y = (self.height - BALL_SIZE)//2
        self.serve(direction=None)
        # Emit a machine-readable state line so external validators can observe objects and scores
        print(f"[STATE] PADDLES L={self.left_paddle.topleft} R={self.right_paddle.topleft} BALL={self.ball.topleft} SCORE={self.score1}-{self.score2}")
        # Emit a machine-readable state line so external validators can observe objects and scores
        print(f"[STATE] PADDLES L={self.left_paddle.topleft} R={self.right_paddle.topleft} BALL={self.ball.topleft} SCORE={self.score1}-{self.score2}")

    def serve(self, direction=None) -> None:
        """Place ball in center and give it an initial diagonal velocity.
        direction: -1 (left), 1 (right), or None for random
        """
        self.ball.x = (self.width - BALL_SIZE)//2
        self.ball.y = (self.height - BALL_SIZE)//2
        if direction not in (-1, 1):
            direction = random.choice([-1, 1])
        vert = random.choice([-1, 1])
        self.ball_vx = BALL_SPEED * direction
        self.ball_vy = BALL_SPEED * 0.6 * vert  # make diagonal but not 45deg

    def handle_events(self) -> bool:
        """Process pygame events. Returns False when the game should quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_r:
                    # Reset game
                    self.reset()
        return True

    def update(self, dt: float) -> None:
        """Advance game state by dt seconds. Movement is frozen when game_over is True."""
        if self.game_over:
            return

        keys = pygame.key.get_pressed()
        # Left paddle: W/S
        if keys[pygame.K_w]:
            self.left_paddle.y -= int(PADDLE_SPEED * dt)
        if keys[pygame.K_s]:
            self.left_paddle.y += int(PADDLE_SPEED * dt)
        # Right paddle: UP/DOWN
        if keys[pygame.K_UP]:
            self.right_paddle.y -= int(PADDLE_SPEED * dt)
        if keys[pygame.K_DOWN]:
            self.right_paddle.y += int(PADDLE_SPEED * dt)

        # Clamp paddles to screen
        self.left_paddle.y = max(0, min(self.left_paddle.y, self.height - PADDLE_HEIGHT))
        self.right_paddle.y = max(0, min(self.right_paddle.y, self.height - PADDLE_HEIGHT))

        # Move ball
        self.ball.x += int(self.ball_vx * dt)
        self.ball.y += int(self.ball_vy * dt)

        # Ball collision with top/bottom
        if self.ball.top <= 0:
            self.ball.top = 0
            self.ball_vy *= -1
        if self.ball.bottom >= self.height:
            self.ball.bottom = self.height
            self.ball_vy *= -1

        # Ball collision with paddles
        if self.ball.colliderect(self.left_paddle) and self.ball_vx < 0:
            self.ball.left = self.left_paddle.right
            self.ball_vx *= -1
            # tweak vertical velocity based on contact point
            offset = (self.ball.centery - self.left_paddle.centery) / (PADDLE_HEIGHT/2)
            self.ball_vy = BALL_SPEED * 0.8 * offset
        if self.ball.colliderect(self.right_paddle) and self.ball_vx > 0:
            self.ball.right = self.right_paddle.left
            self.ball_vx *= -1
            offset = (self.ball.centery - self.right_paddle.centery) / (PADDLE_HEIGHT/2)
            self.ball_vy = BALL_SPEED * 0.8 * offset

        # Scoring: ball goes off left or right
        if self.ball.right < 0:
            # Player 2 scores
            self.score2 += 1
            print(f"[EVENT] SCORE: P2 {self.score2}")
            if self.score2 >= WIN_SCORE:
                self.game_over = True
                self.winner = 2
                print("[EVENT] WIN: Player 2")
                # freeze velocities
                self.ball_vx = 0
                self.ball_vy = 0
                return
            self.serve(direction=1)
        elif self.ball.left > self.width:
            # Player 1 scores
            self.score1 += 1
            print(f"[EVENT] SCORE: P1 {self.score1}")
            if self.score1 >= WIN_SCORE:
                self.game_over = True
                self.winner = 1
                print("[EVENT] WIN: Player 1")
                self.ball_vx = 0
                self.ball_vy = 0
                return
            self.serve(direction=-1)

    def draw(self, screen) -> None:
        """Render the current game state to the provided screen surface."""
        # background
        screen.fill((0, 0, 0))

        # center dashed line
        for y in range(0, self.height, 20):
            pygame.draw.line(screen, (200, 200, 200), (self.width//2, y), (self.width//2, y+10), 2)

        # paddles
        pygame.draw.rect(screen, (255, 255, 255), self.left_paddle)
        pygame.draw.rect(screen, (255, 255, 255), self.right_paddle)

        # ball
        pygame.draw.ellipse(screen, (255, 255, 255), self.ball)

        # scores and controls
        score1_surf = self.font.render(str(self.score1), True, (255, 255, 255))
        score2_surf = self.font.render(str(self.score2), True, (255, 255, 255))
        screen.blit(score1_surf, (self.width//4 - score1_surf.get_width()//2, 20))
        screen.blit(score2_surf, (3*self.width//4 - score2_surf.get_width()//2, 20))

        controls = "W/S: Left    UP/DOWN: Right    R: Reset    Esc: Quit"
        ctrl_surf = self.small_font.render(controls, True, (180, 180, 180))
        screen.blit(ctrl_surf, (self.width//2 - ctrl_surf.get_width()//2, 5))

        # Winner message
        if self.game_over and self.winner is not None:
            msg = f"Player {self.winner} wins! Press R to restart"
            msg_surf = self.font.render(msg, True, (255, 220, 0))
            screen.blit(msg_surf, (self.width//2 - msg_surf.get_width()//2, self.height//2 - msg_surf.get_height()//2))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Pong")
    clock = pygame.time.Clock()

    game = Game(WIDTH, HEIGHT)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        running = game.handle_events()
        game.update(dt)
        game.draw(screen)
        pygame.display.flip()

    pygame.quit()


if __name__ == '__main__':
    main()
