import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
from pygame.locals import QUIT, KEYDOWN, KEYUP, K_LEFT, K_RIGHT, K_SPACE, K_r, K_ESCAPE

from level import Level
from player import Player
from camera import Camera
from ui import UI

SCREEN_W = 800
SCREEN_H = 600
FPS = 60

def print_event(line: str):
    print(line, flush=True)

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Pip's Hop")
        self.clock = pygame.time.Clock()
        self.level = Level()
        self.player = Player(*self.level.start_pos)
        self.camera = Camera(SCREEN_W, self.level.width)
        self.ui = UI()
        self.score = 0
        self.lives = 3
        self.state = 'playing'  # playing, win, game_over
        self.last_score_print = None
        # input state
        self.holding_left = False
        self.holding_right = False

    def reset(self):
        self.level.reset()
        self.player = Player(*self.level.start_pos)
        self.camera = Camera(SCREEN_W, self.level.width)
        self.score = 0
        self.lives = 3
        self.state = 'playing'
        print_event('RESTART')

    def lose_life(self):
        self.lives -= 1
        print_event('LIFE LOST')
        if self.lives <= 0:
            self.state = 'game_over'
            print_event('GAME OVER')
        else:
            # respawn player at start
            self.player = Player(*self.level.start_pos)

    def add_score(self, amount):
        self.score += amount
        print_event(f'SCORE:{self.score}')

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == QUIT:
                print_event('QUIT')
                pygame.quit()
                sys.exit()
            if event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    print_event('QUIT')
                    pygame.quit()
                    sys.exit()
                if event.key == K_r:
                    # Restart regardless of state
                    self.reset()
                if self.state != 'playing':
                    # when not playing, only allow restart/quit
                    continue
                if event.key == K_LEFT:
                    self.holding_left = True
                    self.player.move(-1)
                    print_event('DIRECTION left')
                if event.key == K_RIGHT:
                    self.holding_right = True
                    self.player.move(1)
                    print_event('DIRECTION right')
                if event.key == K_SPACE:
                    self.player.jump()
                    print_event('JUMP')
            if event.type == KEYUP:
                if event.key == K_LEFT:
                    self.holding_left = False
                    # if right is held, move right
                    if self.holding_right:
                        self.player.move(1)
                        print_event('DIRECTION right')
                    else:
                        self.player.move(0)
                        print_event('DIRECTION none')
                if event.key == K_RIGHT:
                    self.holding_right = False
                    if self.holding_left:
                        self.player.move(-1)
                        print_event('DIRECTION left')
                    else:
                        self.player.move(0)
                        print_event('DIRECTION none')

    def update(self, dt):
        if self.state != 'playing':
            return
        # update player
        self.player.update(dt, self.level.platforms)
        # Camera follow
        self.camera.update(self.player.rect)
        # check falling below screen
        if self.player.rect.top > SCREEN_H:
            self.lose_life()
        # update enemies
        for e in self.level.enemies:
            e.update(dt)
        # check player-enemy collisions
        for e in self.level.enemies:
            if not e.alive:
                continue
            if self.player.rect.colliderect(e.rect):
                # determine if stomp
                # if player's bottom was above enemy's top and player is moving down
                if self.player.vel_y > 0 and self.player.rect.bottom - e.rect.top < 20:
                    # stomp
                    e.on_stomped()
                    self.player.vel_y = -250  # bounce
                    self.add_score(100)
                else:
                    # side collision
                    self.lose_life()
        # check coins
        for c in self.level.coins:
            if not c.collected and self.player.rect.colliderect(c.rect):
                c.collected = True
                self.add_score(10)
        # flagpole
        if self.player.rect.colliderect(self.level.flagpole.rect):
            self.state = 'win'
            print_event('WIN')

    def draw(self):
        # background
        self.screen.fill((100, 149, 237))  # cornflower blue
        # draw platforms
        for p in self.level.platforms:
            p.draw(self.screen, self.camera.offset_x)
        # draw coins
        for c in self.level.coins:
            c.draw(self.screen, self.camera.offset_x)
        # draw enemies
        for e in self.level.enemies:
            e.draw(self.screen, self.camera.offset_x)
        # draw flagpole
        self.level.flagpole.draw(self.screen, self.camera.offset_x)
        # draw player
        self.player.draw(self.screen, self.camera.offset_x)
        # draw UI
        controls = 'Arrows: Move, Space: Jump, R: Restart, Esc: Quit'
        self.ui.draw(self.screen, self.score, self.lives, controls)
        # freeze overlay if ended
        if self.state == 'win':
            # draw translucent overlay
            s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            s.fill((0,0,0,120))
            self.screen.blit(s, (0,0))
            # show WIN text
            font = pygame.font.Font(None, 72)
            txt = font.render('YOU WIN', True, (255,255,255))
            self.screen.blit(txt, (SCREEN_W//2 - txt.get_width()//2, SCREEN_H//2 - txt.get_height()//2))
        if self.state == 'game_over':
            s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            s.fill((0,0,0,180))
            self.screen.blit(s, (0,0))
            font = pygame.font.Font(None, 72)
            txt = font.render('GAME OVER', True, (255,0,0))
            self.screen.blit(txt, (SCREEN_W//2 - txt.get_width()//2, SCREEN_H//2 - txt.get_height()//2))

    def run(self):
        while True:
            dt_ms = self.clock.tick(FPS)
            dt = dt_ms / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()

if __name__ == '__main__':
    game = Game()
    game.run()
