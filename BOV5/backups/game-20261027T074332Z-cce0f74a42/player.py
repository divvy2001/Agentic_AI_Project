import pygame

class Player:
    def __init__(self, x, y, size=30):
        self.size = size
        self.rect = pygame.Rect(x, y, size, size)
        self.color = (255, 165, 0)  # orange
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.speed = 220.0  # px/s
        self.jump_vel = -420.0  # px/s
        self.gravity = 1200.0  # px/s^2
        self.on_ground = False
        self.direction = 0  # -1 left, 0 none, 1 right

    def move(self, direction: int):
        # direction is -1, 0, or 1
        self.direction = direction
        if direction == -1:
            self.vel_x = -self.speed
        elif direction == 1:
            self.vel_x = self.speed
        else:
            self.vel_x = 0

    def jump(self):
        if self.on_ground:
            self.vel_y = self.jump_vel
            self.on_ground = False

    def update(self, dt: float, platforms: list):
        # dt in seconds
        # Horizontal movement
        self.rect.x += int(self.vel_x * dt)
        # Horizontal collisions
        for p in platforms:
            if self.rect.colliderect(p.rect):
                if self.vel_x > 0:
                    self.rect.right = p.rect.left
                elif self.vel_x < 0:
                    self.rect.left = p.rect.right
                self.vel_x = 0
        # Vertical movement
        self.vel_y += self.gravity * dt
        self.rect.y += int(self.vel_y * dt)
        self.on_ground = False
        for p in platforms:
            if self.rect.colliderect(p.rect):
                # falling
                if self.vel_y > 0:
                    self.rect.bottom = p.rect.top
                    self.vel_y = 0
                    self.on_ground = True
                elif self.vel_y < 0:
                    self.rect.top = p.rect.bottom
                    self.vel_y = 0

    def draw(self, surface, offset_x):
        screen_rect = self.rect.move(-offset_x, 0)
        pygame.draw.rect(surface, self.color, screen_rect)
