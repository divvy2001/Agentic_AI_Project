import pygame

class Platform:
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)

    def draw(self, surface, offset_x, color=(139,69,19)):
        # brown platform by default
        screen_rect = self.rect.move(-offset_x, 0)
        pygame.draw.rect(surface, color, screen_rect)
