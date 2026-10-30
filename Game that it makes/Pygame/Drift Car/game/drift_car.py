import sys
import math
from pathlib import Path
import pygame

# Entry point for the Drift Car game
# Implements Car and Game classes and provides run() when executed.

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

ASSETS_DIR = Path(__file__).resolve().parent / 'assets'
CAR_SPRITE = ASSETS_DIR / 'car_sprite.png'
BG_IMAGE = ASSETS_DIR / 'desert_canyon_background.png'

class Car:
    """Car state and behavior.

    Public attributes:
      pos: pygame.Vector2 (pixels)
      vel: pygame.Vector2 (pixels/sec)
      heading: float (radians, 0 = right, increases CCW)
    """
    def __init__(self, start_pos, start_heading=0.0, sprite=None):
        self.start_pos = pygame.Vector2(start_pos)
        self.start_heading = start_heading
        self.pos = pygame.Vector2(start_pos)
        self.vel = pygame.Vector2(0, 0)
        self.heading = start_heading
        self.sprite = sprite
        self.width = 64
        self.height = 32

        # physics params
        self.acceleration = 300.0  # pixels / s^2
        self.brake_accel = 400.0
        self.max_speed = 450.0
        self.max_reverse = -150.0
        self.friction = 200.0  # deceleration when no accel
        self.lateral_damping = 3.0  # how fast lateral slippage is removed
        self.turn_speed = math.radians(120)  # radians per second at full input

    def rect(self):
        # return rectangle centered on pos
        return pygame.Rect(int(self.pos.x - self.width/2), int(self.pos.y - self.height/2), self.width, self.height)

    def reset(self):
        self.pos = pygame.Vector2(self.start_pos)
        self.vel = pygame.Vector2(0, 0)
        self.heading = self.start_heading

    def update(self, dt, inputs):
        """Update car physics.

        inputs: dict with booleans 'accel','brake','left','right'
        """
        # orientation vector
        forward = pygame.Vector2(math.cos(self.heading), math.sin(self.heading))
        # decompose velocity
        forward_speed = self.vel.dot(forward)
        lateral = self.vel - forward * forward_speed

        # steering rotates heading (does not immediately rotate velocity) -> drift
        # steering: left turns counter-clockwise (increase heading), right turns clockwise (decrease)
        if inputs.get('left'):
            self.heading += self.turn_speed * dt
        if inputs.get('right'):
            self.heading -= self.turn_speed * dt

        # acceleration/braking affect forward_speed
        if inputs.get('accel'):
            forward_speed += self.acceleration * dt
        elif inputs.get('brake'):
            # apply strong braking; allow reversing
            forward_speed -= self.brake_accel * dt
        else:
            # friction when no accel/brake: reduce forward_speed towards zero
            if forward_speed > 0:
                forward_speed = max(0.0, forward_speed - self.friction * dt)
            elif forward_speed < 0:
                forward_speed = min(0.0, forward_speed + self.friction * dt)

        # clamp speeds
        forward_speed = max(self.max_reverse, min(self.max_speed, forward_speed))

        # damp lateral velocity to simulate gradual alignment
        lateral *= max(0.0, 1.0 - self.lateral_damping * dt)

        # recombine velocity (note heading may have changed since forward vector computed)
        forward_now = pygame.Vector2(math.cos(self.heading), math.sin(self.heading))
        self.vel = forward_now * forward_speed + lateral

        # update position
        self.pos += self.vel * dt

    def draw(self, surface):
        if self.sprite:
            # rotate sprite to heading (convert radians to degrees). Pygame rotates CCW.
            angle_deg = -math.degrees(self.heading)
            rotated = pygame.transform.rotozoom(self.sprite, angle_deg, 1.0)
            rect = rotated.get_rect(center=(int(self.pos.x), int(self.pos.y)))
            surface.blit(rotated, rect.topleft)
        else:
            # draw simple rectangle if sprite missing
            r = self.rect()
            pygame.draw.rect(surface, (255, 0, 0), r)


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Drift Car')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)

        # load assets
        self.bg_image = None
        self.car_sprite = None
        try:
            if BG_IMAGE.exists():
                self.bg_image = pygame.image.load(str(BG_IMAGE)).convert()
            if CAR_SPRITE.exists():
                self.car_sprite = pygame.image.load(str(CAR_SPRITE)).convert_alpha()
        except Exception:
            # asset load failures are tolerated but reported in console
            print('Warning: failed to load images', file=sys.stderr)

        # track geometry: donut-shaped track using outer and inner rects
        self.outer_rect = pygame.Rect(50, 50, SCREEN_WIDTH - 100, SCREEN_HEIGHT - 100)
        self.inner_rect = pygame.Rect(200, 150, SCREEN_WIDTH - 400, SCREEN_HEIGHT - 300)

        # lap lines: vertical segments
        self.start_line_x = self.outer_rect.right - 60  # near right side
        self.checkpoint_x = self.outer_rect.left + 60   # near left side
        self.line_y1 = SCREEN_HEIGHT // 2 - 80
        self.line_y2 = SCREEN_HEIGHT // 2 + 80

        # initial car
        start_pos = (self.start_line_x - 40, SCREEN_HEIGHT // 2)
        self.car = Car(start_pos, start_heading=math.pi, sprite=self.car_sprite)

        # gameplay state
        self.laps = 0
        self.passed_checkpoint = False
        self.prev_pos = pygame.Vector2(self.car.pos)
        self.running = True

        # input state
        self.inputs = {'accel': False, 'brake': False, 'left': False, 'right': False}

        # freeze after lap increment? Plan says freeze only on WIN/LOSE; no win implemented.
        self.frozen = False

    def reset(self):
        self.car.reset()
        self.laps = 0
        self.passed_checkpoint = False
        self.prev_pos = pygame.Vector2(self.car.pos)

    def check_collision(self):
        # if car goes outside outer_rect or inside inner_rect -> collision with wall
        r = self.car.rect()
        collided = False
        if not self.outer_rect.contains(r):
            collided = True
        if self.inner_rect.colliderect(r):
            collided = True
        return collided

    def handle_collision(self):
        # On collision, briefly stop forward momentum and push back to previous pos
        # Stop forward component
        forward = pygame.Vector2(math.cos(self.car.heading), math.sin(self.car.heading))
        forward_speed = self.car.vel.dot(forward)
        lateral = self.car.vel - forward * forward_speed
        # zero forward speed, retain small lateral
        self.car.vel = lateral * 0.2
        # push back
        self.car.pos = pygame.Vector2(self.prev_pos)

    def check_lap_lines(self):
        # detect crossing checkpoint and start line using x coordinate crossing and y-range
        y = self.car.pos.y
        py = self.prev_pos.y
        if not (self.line_y1 <= y <= self.line_y2):
            return
        # crossing checkpoint from right to left
        if (self.prev_pos.x > self.checkpoint_x) and (self.car.pos.x <= self.checkpoint_x):
            self.passed_checkpoint = True
        # crossing start line from left to right
        if (self.prev_pos.x < self.start_line_x) and (self.car.pos.x >= self.start_line_x):
            if self.passed_checkpoint:
                self.laps += 1
                self.passed_checkpoint = False
                print('LAP COMPLETE', flush=True)

    def draw_track(self):
        # background
        if self.bg_image:
            bg_scaled = pygame.transform.scale(self.bg_image, self.screen.get_size())
            self.screen.blit(bg_scaled, (0, 0))
        else:
            self.screen.fill((240, 200, 160))  # sandy background

        # draw outer area as rock cliffs (walls)
        pygame.draw.rect(self.screen, (120, 80, 40), self.outer_rect, 0)
        # draw road by drawing inner rect with background color to cut a hole
        pygame.draw.rect(self.screen, (60, 60, 60), self.inner_rect, 0)
        # To make track road visible: fill between outer and inner as road
        # (We already drew outer as rock and inner as road; now draw road area properly)
        # Instead, draw road as outer minus inner: draw a large rect of road, then draw inner rect with bg
        road_rect = pygame.Rect(self.outer_rect)
        pygame.draw.rect(self.screen, (80, 80, 80), road_rect, 0)
        pygame.draw.rect(self.screen, (240, 200, 160), self.inner_rect, 0)

        # draw walls as outlines
        pygame.draw.rect(self.screen, (30, 30, 30), self.outer_rect, 4)
        pygame.draw.rect(self.screen, (30, 30, 30), self.inner_rect, 4)

        # draw lap start and checkpoint lines as plain colored shapes
        pygame.draw.line(self.screen, (255, 0, 0), (self.start_line_x, self.line_y1), (self.start_line_x, self.line_y2), 4)
        pygame.draw.line(self.screen, (0, 255, 0), (self.checkpoint_x, self.line_y1), (self.checkpoint_x, self.line_y2), 4)

    def draw_hud(self):
        # lap counter top-left
        txt = f"Laps: {self.laps}"
        surf = self.font.render(txt, True, (255, 255, 255))
        self.screen.blit(surf, (10, 10))

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print('QUIT', flush=True)
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        print('QUIT', flush=True)
                        self.running = False
                    elif event.key == pygame.K_r:
                        print('RESTART', flush=True)
                        self.reset()
                    elif event.key == pygame.K_UP:
                        self.inputs['accel'] = True
                        print('ACCELERATE', flush=True)
                    elif event.key == pygame.K_DOWN:
                        self.inputs['brake'] = True
                        print('BRAKE', flush=True)
                    elif event.key == pygame.K_LEFT:
                        self.inputs['left'] = True
                        print('TURN LEFT', flush=True)
                    elif event.key == pygame.K_RIGHT:
                        self.inputs['right'] = True
                        print('TURN RIGHT', flush=True)
                elif event.type == pygame.KEYUP:
                    if event.key == pygame.K_UP:
                        self.inputs['accel'] = False
                    elif event.key == pygame.K_DOWN:
                        self.inputs['brake'] = False
                    elif event.key == pygame.K_LEFT:
                        self.inputs['left'] = False
                    elif event.key == pygame.K_RIGHT:
                        self.inputs['right'] = False

            if not self.frozen:
                # update physics
                self.prev_pos = pygame.Vector2(self.car.pos)
                self.car.update(dt, self.inputs)

                # collision
                if self.check_collision():
                    self.handle_collision()

                # lap detection
                self.check_lap_lines()

            # draw everything
            self.draw_track()
            self.car.draw(self.screen)
            # draw lap count
            self.draw_hud()

            pygame.display.flip()

        pygame.quit()


def main():
    game = Game()
    game.run()


if __name__ == '__main__':
    main()
