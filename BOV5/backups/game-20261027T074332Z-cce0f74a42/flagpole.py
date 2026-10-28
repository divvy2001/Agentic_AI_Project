import pygame

class Flagpole:
    def __init__(self, x, y, w=20, h=120):
        # y is top of pole
        self.rect = pygame.Rect(x, y, w, h)
        self.color = (0, 200, 0)  # green

    def draw(self, surface, offset_x):
        screen_rect = self.rect.move(-offset_x, 0)
        pygame.draw.rect(surface, self.color, screen_rect)
