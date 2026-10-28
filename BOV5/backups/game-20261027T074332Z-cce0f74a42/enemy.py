import pygame

class Enemy:
    def __init__(self, x, y, w=30, h=30, speed=60, patrol_min=None, patrol_max=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.color = (128, 0, 128)  # purple
        self.speed = speed
        self.vx = speed
        self.alive = True
        # patrol range in world coordinates
        self.patrol_min = patrol_min if patrol_min is not None else x - 100
        self.patrol_max = patrol_max if patrol_max is not None else x + 100

    def update(self, dt: float):
        if not self.alive:
            return
        self.rect.x += int(self.vx * dt)
        if self.rect.x < self.patrol_min:
            self.rect.x = self.patrol_min
            self.vx = abs(self.vx)
        elif self.rect.x > self.patrol_max:
            self.rect.x = self.patrol_max
            self.vx = -abs(self.vx)

    def on_stomped(self):
        self.alive = False

    def draw(self, surface, offset_x):
        if not self.alive:
            return
        screen_rect = self.rect.move(-offset_x, 0)
        pygame.draw.rect(surface, self.color, screen_rect)
