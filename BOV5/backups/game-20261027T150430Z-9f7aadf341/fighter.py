import pygame
from pathlib import Path
from game import constants as C

class Fighter:
    """
    Fighter represents a player or AI-controlled fighter.

    Methods:
    - update(dt: float, floor_y: int, target: 'Fighter'|None=None)
    - draw(surface: pygame.Surface)
    - punch() -> bool
    - check_punch_hit(other: 'Fighter') -> bool
    - take_damage(amount: int)
    - apply_knockback(amount: float)

    Attributes are kept public for simplicity (position via rect, health etc.).
    """

    def __init__(self, x: float, image_path: str, facing: str = 'right', is_ai: bool = False):
        self.is_ai = is_ai
        self.facing = facing  # 'left' or 'right'
        self.image = pygame.image.load(image_path).convert_alpha()
        self.rect = self.image.get_rect()
        # anchor by midbottom to the given x; caller should set rect.midbottom after init
        self.rect.centerx = int(x)
        self.vx = 0.0
        self.vy = 0.0

        self.health = C.MAX_HEALTH

        # Punch state
        self.is_punching = False
        self.punch_timer = 0.0
        # cooldown timer until can punch again
        self.cooldown_timer = 0.0
        self.punch_range = C.PUNCH_RANGE
        self.punch_damage = C.PUNCH_DAMAGE
        self.punch_hit_registered = False

        # Flash when hit
        self.flash_timer = 0.0

    def rect_midbottom(self):
        return self.rect.midbottom

    def update(self, dt: float, floor_y: int, target: 'Fighter' = None):
        """Update physics and AI. If target is provided and is_ai True, the fighter will move/punch toward target."""
        # Apply gravity
        self.vy += C.GRAVITY * dt
        # Integrate position
        self.rect.x += int(self.vx * dt)
        self.rect.y += int(self.vy * dt)

        # Floor collision
        if self.rect.bottom >= floor_y:
            self.rect.bottom = floor_y
            # If falling, stop vertical velocity
            if self.vy > 0:
                self.vy = 0

        # Timers
        if self.is_punching:
            self.punch_timer -= dt
            if self.punch_timer <= 0:
                self.is_punching = False
                self.punch_timer = 0
                # reset hit registration so future punches can hit
                self.punch_hit_registered = False
        if self.cooldown_timer > 0:
            self.cooldown_timer -= dt
            if self.cooldown_timer < 0:
                self.cooldown_timer = 0
        if self.flash_timer > 0:
            self.flash_timer -= dt
            if self.flash_timer < 0:
                self.flash_timer = 0

        # AI behavior
        if self.is_ai and target is not None:
            self._ai_behavior(dt, target)

    def _ai_behavior(self, dt: float, target: 'Fighter'):
        # Walk toward the player
        if target.rect.centerx < self.rect.centerx - 5:
            # player is left
            self.vx = -C.AI_SPEED
            self.facing = 'left'
        elif target.rect.centerx > self.rect.centerx + 5:
            self.vx = C.AI_SPEED
            self.facing = 'right'
        else:
            self.vx = 0

        # If close, attempt to punch
        distance = abs(target.rect.centerx - self.rect.centerx)
        if distance <= C.AI_PUNCH_DISTANCE and self.cooldown_timer <= 0 and not self.is_punching:
            # Start punch
            self.punch()
            # AI uses its cooldown
            self.cooldown_timer = C.AI_PUNCH_COOLDOWN

    def start_move(self, direction: str):
        if direction == 'left':
            self.vx = -C.MOVE_SPEED
            self.facing = 'left'
        elif direction == 'right':
            self.vx = C.MOVE_SPEED
            self.facing = 'right'

    def stop_move(self):
        self.vx = 0

    def jump(self):
        # Only allow jump if on floor
        if self.vy == 0:
            self.vy = -C.JUMP_SPEED
            return True
        return False

    def punch(self) -> bool:
        # Start punch if not in cooldown
        if self.cooldown_timer <= 0 and not self.is_punching:
            self.is_punching = True
            self.punch_timer = C.PUNCH_DURATION
            # set cooldown (player and AI may have different cooldown handled by caller)
            # register hit false until we actually hit
            self.punch_hit_registered = False
            return True
        return False

    def check_punch_hit(self, other: 'Fighter') -> bool:
        """Check whether this fighter's current punch hits the other. If it does, apply damage and knockback and return True."""
        if not self.is_punching:
            return False
        if self.punch_hit_registered:
            return False

        # Build punch rect in front of fighter
        if self.facing == 'right':
            punch_rect = pygame.Rect(self.rect.right, self.rect.top + 10, self.punch_range, self.rect.height - 20)
        else:
            punch_rect = pygame.Rect(self.rect.left - self.punch_range, self.rect.top + 10, self.punch_range, self.rect.height - 20)

        if punch_rect.colliderect(other.rect):
            # Register hit so one punch only hits once
            self.punch_hit_registered = True
            other.take_damage(self.punch_damage)
            # Knockback: per Plan, opponent x-position decreases if attacker facing right, increases if facing left
            if self.facing == 'right':
                other.apply_knockback(-C.KNOCKBACK)
            else:
                other.apply_knockback(C.KNOCKBACK)
            # Flash other
            other.flash_timer = C.FLASH_TIME
            return True
        return False

    def take_damage(self, amount: int):
        self.health -= int(amount)
        if self.health < 0:
            self.health = 0

    def apply_knockback(self, amount: float):
        # Move the rect horizontally by amount pixels
        self.rect.x += int(amount)

    def draw(self, surface: pygame.Surface):
        surface.blit(self.image, self.rect)
        # Draw flash overlay if needed
        if self.flash_timer > 0:
            overlay = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
            overlay.fill((255, 255, 255, 160))
            surface.blit(overlay, self.rect)

    def is_alive(self):
        return self.health > 0
