import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
from pathlib import Path
from game import constants as C
from game.fighter import Fighter

ASSET_DIR = Path(__file__).resolve().parent / 'assets'


def load_asset(name: str) -> str:
    path = ASSET_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing asset: {path}")
    return str(path)


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))
        pygame.display.set_caption('Dojo Duel')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.big_font = pygame.font.Font(None, 72)

        self.running = True
        self.state = 'playing'  # 'playing' or 'ended'

        # Input flags
        self.moving_left = False
        self.moving_right = False

        self._load_assets()
        self.init_game()

    def _load_assets(self):
        # Load fighter images paths
        self.red_path = load_asset('red_belt_fighter.png')
        self.blue_path = load_asset('blue_belt_fighter.png')

    def init_game(self):
        # Create fighters
        # Player on left
        player_x = 150
        rival_x = C.SCREEN_WIDTH - 150
        self.player = Fighter(player_x, self.red_path, facing='right', is_ai=False)
        self.rival = Fighter(rival_x, self.blue_path, facing='left', is_ai=True)
        # Anchor to floor
        self.player.rect.midbottom = (player_x, C.FLOOR_Y)
        self.rival.rect.midbottom = (rival_x, C.FLOOR_Y)

        # Reset additional state
        self.player.health = C.MAX_HEALTH
        self.rival.health = C.MAX_HEALTH
        self.player.cooldown_timer = 0
        self.rival.cooldown_timer = 0
        self.player.is_punching = False
        self.rival.is_punching = False
        self.player.punch_timer = 0
        self.rival.punch_timer = 0
        self.player.flash_timer = 0
        self.rival.flash_timer = 0

        self.state = 'playing'
        self.last_end_printed = False

    def run(self):
        while self.running:
            dt = self.clock.tick(C.FPS) / 1000.0
            self._handle_events()
            if self.state == 'playing':
                self._update(dt)
                self._check_hits()
                self._check_end()
            self._draw()
            pygame.display.flip()
        pygame.quit()

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                print('QUIT', flush=True)
                self.running = False
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    print('QUIT', flush=True)
                    self.running = False
                    return
                if event.key == pygame.K_r:
                    # Restart
                    print('RESTART', flush=True)
                    self.init_game()
                if self.state != 'playing':
                    # When ended, only allow restart/quit
                    continue
                if event.key == pygame.K_LEFT:
                    self.moving_left = True
                    self.player.start_move('left')
                    print('MOVE LEFT', flush=True)
                elif event.key == pygame.K_RIGHT:
                    self.moving_right = True
                    self.player.start_move('right')
                    print('MOVE RIGHT', flush=True)
                elif event.key == pygame.K_UP:
                    if self.player.jump():
                        print('JUMP', flush=True)
                elif event.key == pygame.K_SPACE:
                    started = self.player.punch()
                    if started:
                        # apply player cooldown
                        self.player.cooldown_timer = C.PUNCH_COOLDOWN
                        print('PUNCH', flush=True)
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_LEFT:
                    self.moving_left = False
                    # if right still held, move right
                    if self.moving_right:
                        self.player.start_move('right')
                    else:
                        self.player.stop_move()
                elif event.key == pygame.K_RIGHT:
                    self.moving_right = False
                    if self.moving_left:
                        self.player.start_move('left')
                    else:
                        self.player.stop_move()

    def _update(self, dt: float):
        # Update fighters
        # Player update
        self.player.update(dt, C.FLOOR_Y)
        # Rival update with AI
        self.rival.update(dt, C.FLOOR_Y, target=self.player)

    def _check_hits(self):
        # Player punch hits rival
        if self.player.check_punch_hit(self.rival):
            # Print damage event? Not required; health bar updates visually
            pass
        # Rival punch hits player
        if self.rival.check_punch_hit(self.player):
            pass

    def _check_end(self):
        if not self.rival.is_alive():
            self.state = 'ended'
            if not self.last_end_printed:
                print('WIN', flush=True)
                self.last_end_printed = True
        elif not self.player.is_alive():
            self.state = 'ended'
            if not self.last_end_printed:
                print('GAME OVER', flush=True)
                self.last_end_printed = True

    def _draw(self):
        # Background
        self.screen.fill(C.LIGHT_BG)
        # Floor
        pygame.draw.rect(self.screen, C.WOOD_BROWN, (0, C.FLOOR_Y, C.SCREEN_WIDTH, C.FLOOR_HEIGHT))

        # Fighters
        self.player.draw(self.screen)
        self.rival.draw(self.screen)

        # Health bars
        # Player bar (left)
        pb_x = C.HEALTH_BAR_MARGIN
        pb_y = C.HEALTH_BAR_MARGIN
        pygame.draw.rect(self.screen, C.HEALTH_BG, (pb_x, pb_y, C.HEALTH_BAR_WIDTH, C.HEALTH_BAR_HEIGHT))
        player_w = int((self.player.health / C.MAX_HEALTH) * C.HEALTH_BAR_WIDTH)
        pygame.draw.rect(self.screen, C.HEALTH_PLAYER, (pb_x, pb_y, player_w, C.HEALTH_BAR_HEIGHT))
        player_text = self.font.render('Player', True, C.BLACK)
        self.screen.blit(player_text, (pb_x, pb_y + C.HEALTH_BAR_HEIGHT + 4))

        # Rival bar (right)
        rb_x = C.SCREEN_WIDTH - C.HEALTH_BAR_MARGIN - C.HEALTH_BAR_WIDTH
        rb_y = C.HEALTH_BAR_MARGIN
        pygame.draw.rect(self.screen, C.HEALTH_BG, (rb_x, rb_y, C.HEALTH_BAR_WIDTH, C.HEALTH_BAR_HEIGHT))
        rival_w = int((self.rival.health / C.MAX_HEALTH) * C.HEALTH_BAR_WIDTH)
        pygame.draw.rect(self.screen, C.HEALTH_RIVAL, (rb_x + (C.HEALTH_BAR_WIDTH - rival_w), rb_y, rival_w, C.HEALTH_BAR_HEIGHT))
        rival_text = self.font.render('Rival', True, C.BLACK)
        self.screen.blit(rival_text, (rb_x + C.HEALTH_BAR_WIDTH - rival_text.get_width(), rb_y + C.HEALTH_BAR_HEIGHT + 4))

        # If ended, display message and freeze
        if self.state == 'ended':
            if not self.player.is_alive():
                msg = 'GAME OVER'
            else:
                msg = 'WIN'
            text_surf = self.big_font.render(msg, True, C.BLACK)
            self.screen.blit(text_surf, ((C.SCREEN_WIDTH - text_surf.get_width()) // 2, (C.SCREEN_HEIGHT - text_surf.get_height()) // 2))


if __name__ == '__main__':
    game = Game()
    game.run()
