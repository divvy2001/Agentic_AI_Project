import pygame
import random
from typing import List, Optional
from game import constants as C

class AlienGrid:
    """Manages a grid of aliens and their bullets.

    Public attributes:
    - aliens: List[pygame.Rect]
    - bullets: List[pygame.Rect]

    Methods:
    - update(dt: float) -> None
    - check_collision(bullet: pygame.Rect) -> bool
    - any_reached(y_threshold: int) -> bool
    - is_empty() -> bool
    - reset() -> None
    - draw(surface) -> None
    """
    def __init__(self, rows: int = C.ALIEN_ROWS, cols: int = C.ALIEN_COLS,
                 start_x: int = C.ALIEN_START_X, start_y: int = C.ALIEN_START_Y):
        self.rows = rows
        self.cols = cols
        self.start_x = start_x
        self.start_y = start_y
        self.aliens: List[pygame.Rect] = []
        self.bullets: List[pygame.Rect] = []
        self.direction = 1  # 1 = right, -1 = left
        self.speed = C.ALIEN_SPEED
        self._build_grid()

    def _build_grid(self):
        self.aliens.clear()
        for r in range(self.rows):
            for c in range(self.cols):
                x = self.start_x + c * (C.ALIEN_WIDTH + C.ALIEN_H_PADDING)
                y = self.start_y + r * (C.ALIEN_HEIGHT + C.ALIEN_V_PADDING)
                rect = pygame.Rect(x, y, C.ALIEN_WIDTH, C.ALIEN_HEIGHT)
                self.aliens.append(rect)

    def update(self, dt: float) -> None:
        if not self.aliens:
            return
        dx = int(self.speed * dt * self.direction)
        # Move horizontally
        for a in self.aliens:
            a.x += dx
        # Check edges
        hit_edge = False
        for a in self.aliens:
            if a.left <= 0 and self.direction == -1:
                hit_edge = True
                break
            if a.right >= C.SCREEN_WIDTH and self.direction == 1:
                hit_edge = True
                break
        if hit_edge:
            # reverse and drop
            self.direction *= -1
            for a in self.aliens:
                a.y += C.ALIEN_DROP_Y
        # Update alien bullets
        for b in list(self.bullets):
            b.y += int(C.ALIEN_BULLET_SPEED * dt)
            if b.top > C.SCREEN_HEIGHT:
                self.bullets.remove(b)
        # Possibly spawn a new bullet (global rate)
        if self.aliens and random.random() < C.ALIEN_BULLET_SPAWN_RATE * dt:
            shooter = random.choice(self.aliens)
            bx = shooter.centerx - C.ALIEN_BULLET_WIDTH // 2
            by = shooter.bottom
            self.bullets.append(pygame.Rect(bx, by, C.ALIEN_BULLET_WIDTH, C.ALIEN_BULLET_HEIGHT))

    def check_collision(self, bullet: pygame.Rect) -> bool:
        # If bullet hits any alien, remove that alien and return True
        for a in list(self.aliens):
            if bullet.colliderect(a):
                self.aliens.remove(a)
                return True
        return False

    def any_reached(self, y_threshold: int) -> bool:
        for a in self.aliens:
            if a.bottom >= y_threshold:
                return True
        return False

    def is_empty(self) -> bool:
        return len(self.aliens) == 0

    def reset(self) -> None:
        self.direction = 1
        self.speed = C.ALIEN_SPEED
        self._build_grid()
        self.bullets.clear()

    def draw(self, surface: pygame.Surface) -> None:
        for a in self.aliens:
            pygame.draw.rect(surface, C.GREEN, a)
        for b in self.bullets:
            pygame.draw.rect(surface, C.RED, b)
