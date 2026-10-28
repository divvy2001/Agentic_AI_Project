import pygame

class Coin:
    def __init__(self, x, y, size=16):
        # coin center at (x,y) provided as world coords
        self.rect = pygame.Rect(x - size//2, y - size//2, size, size)
        self.color = (255, 215, 0)  # gold/yellow
        self.collected = False

    def draw(self, surface, offset_x):
        if self.collected:
            return
        screen_rect = self.rect.move(-offset_x, 0)
        pygame.draw.rect(surface, self.color, screen_rect)
