import pygame
from pathlib import Path
from typing import Optional
from game import constants as C

class Player:
    """Player ship and single bullet management.

    Public attributes:
    - rect: pygame.Rect
    - bullet: Optional[pygame.Rect]

    Methods:
    - update(dt: float) -> None
    - move(dx: float) -> None
    - shoot() -> bool
    - reset(x:int,y:int) -> None
    - draw(surface) -> None
    - get_bullet() -> Optional[pygame.Rect]
    """
    def __init__(self, x: int, y: int):
        self.rect = pygame.Rect(x - C.PLAYER_WIDTH // 2, y - C.PLAYER_HEIGHT // 2,
                                C.PLAYER_WIDTH, C.PLAYER_HEIGHT)
        self.bullet: Optional[pygame.Rect] = None

    def update(self, dt: float) -> None:
        # Update player bullet
        if self.bullet:
            self.bullet.y -= int(C.PLAYER_BULLET_SPEED * dt)
            if self.bullet.bottom < 0:
                self.bullet = None

    def move(self, dx: float) -> None:
        # dx is in pixels (not dt-scaled) for convenience; callers should multiply speed*dt
        self.rect.x += int(dx)
        # clamp to screen
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > C.SCREEN_WIDTH:
            self.rect.right = C.SCREEN_WIDTH

    def shoot(self) -> bool:
        if self.bullet is None:
            bx = self.rect.centerx - C.PLAYER_BULLET_WIDTH // 2
            by = self.rect.top - C.PLAYER_BULLET_HEIGHT
            self.bullet = pygame.Rect(bx, by, C.PLAYER_BULLET_WIDTH, C.PLAYER_BULLET_HEIGHT)
            return True
        return False

    def reset(self, x: int, y: int) -> None:
        self.rect.x = x - C.PLAYER_WIDTH // 2
        self.rect.y = y - C.PLAYER_HEIGHT // 2
        self.bullet = None

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, C.BLUE, self.rect)
        if self.bullet:
            pygame.draw.rect(surface, C.YELLOW, self.bullet)

    def get_bullet(self) -> Optional[pygame.Rect]:
        return self.bullet
