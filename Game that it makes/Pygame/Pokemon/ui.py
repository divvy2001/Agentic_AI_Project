import pygame
from typing import Optional
from .creature import Creature
from .battle_manager import BattleManager


class UI:
    FONT_SIZE = 20

    def __init__(self, assets: dict, screen: pygame.Surface):
        self.assets = assets
        self.screen = screen
        self.font = pygame.font.Font(None, self.FONT_SIZE)

    def draw(self, bm: BattleManager, selected_move: int) -> None:
        screen = self.screen
        screen.fill((50, 50, 70))

        # Draw background scaled to center area
        bg = self.assets.get('bg')
        if bg:
            bg_rect = bg.get_rect()
            # draw at top-left corner with some margin
            screen.blit(pygame.transform.scale(bg, (320, 180)), (240, 40))

        # Draw enemy at top-right area
        enemy_img = self.assets.get('shell')
        if enemy_img:
            screen.blit(enemy_img, (520, 70))

        # Draw player at bottom-left area
        ember_img = self.assets.get('ember')
        if ember_img:
            screen.blit(ember_img, (120, 220))

        # Draw names and HP bars
        # Enemy name
        ename = self.font.render(bm.enemy.name, True, (255, 255, 255))
        screen.blit(ename, (520, 40))
        # Enemy HP bar
        self._draw_hp_bar(520, 40 + 24, bm.enemy.hp, bm.enemy.max_hp)

        # Player name
        pname = self.font.render(bm.player.name, True, (255, 255, 255))
        screen.blit(pname, (120, 190))
        self._draw_hp_bar(120, 190 + 24, bm.player.hp, bm.player.max_hp)

        # Draw move list box
        moves_x = 480
        moves_y = 360
        pygame.draw.rect(screen, (30, 30, 30), (moves_x, moves_y, 280, 160))
        for i, move in enumerate(bm.player.moves):
            y = moves_y + 8 + i * 40
            color = (200, 200, 200)
            if i == selected_move and bm.is_input_allowed():
                color = (255, 255, 100)
            text = self.font.render(f"{move['name']}", True, color)
            screen.blit(text, (moves_x + 8, y))

            # small type label
            tlabel = self.font.render(move.get('type', ''), True, (150, 150, 150))
            screen.blit(tlabel, (moves_x + 8 + 140, y))

        # Draw message textbox at bottom
        msg = bm.get_current_message()
        if msg:
            self.draw_textbox(msg)
        elif bm.state == 'win':
            win = self.font.render('WIN', True, (255, 255, 0))
            screen.blit(win, (380, 300))
        elif bm.state == 'lose':
            lose = self.font.render('LOSE', True, (255, 100, 100))
            screen.blit(lose, (380, 300))

    def draw_textbox(self, msg: str) -> None:
        # simple textbox centered at bottom
        rect = pygame.Rect(100, 520, 600, 60)
        pygame.draw.rect(self.screen, (20, 20, 20), rect)
        pygame.draw.rect(self.screen, (200, 200, 200), rect, 2)
        lines = self._wrap_text(msg, 70)
        for i, ln in enumerate(lines):
            t = self.font.render(ln, True, (240, 240, 240))
            self.screen.blit(t, (rect.x + 8, rect.y + 8 + i * 22))

    def _wrap_text(self, text: str, width_chars: int):
        # naive wrap
        words = text.split(' ')
        lines = []
        cur = ''
        for w in words:
            if len(cur) + len(w) + 1 > width_chars:
                lines.append(cur)
                cur = w
            else:
                if cur:
                    cur += ' ' + w
                else:
                    cur = w
        if cur:
            lines.append(cur)
        return lines

    def _draw_hp_bar(self, x: int, y: int, hp: int, max_hp: int) -> None:
        w = 160
        h = 12
        ratio = max(0, hp) / max_hp if max_hp > 0 else 0
        pygame.draw.rect(self.screen, (80, 80, 80), (x, y, w, h))
        pygame.draw.rect(self.screen, (200, 50, 50), (x, y, int(w * ratio), h))
