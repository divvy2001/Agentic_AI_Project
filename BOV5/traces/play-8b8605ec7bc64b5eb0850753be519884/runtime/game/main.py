import sys
import os
# Ensure package imports work both when running "python game/main.py" and "python -m game.main"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
from pygame.locals import *
from typing import Optional

from game.assets import load_assets
from game.creature import Creature
from game.battle_manager import BattleManager
from game.ui import UI


FPS = 60
RESOLUTION = (800, 600)


def create_player_and_enemy():
    # Define moves for Emberkit (player)
    ember_moves = [
        {'name': 'Flame Dash', 'type': 'fire', 'power': 12, 'category': 'damage'},
        {'name': 'Tail Whip', 'type': 'neutral', 'power': 6, 'category': 'damage'},
        {'name': 'Heal', 'type': 'neutral', 'power': 10, 'category': 'heal'},
    ]
    ember = Creature('Emberkit', 'fire', max_hp=40, defense=2, moves=ember_moves)

    # Define moves for Shellwave (enemy)
    shell_moves = [
        {'name': 'Water Spray', 'type': 'water', 'power': 10, 'category': 'damage'},
        {'name': 'Shell Spin', 'type': 'neutral', 'power': 8, 'category': 'damage'},
        {'name': 'Recover', 'type': 'neutral', 'power': 8, 'category': 'heal'},
    ]
    shell = Creature('Shellwave', 'water', max_hp=45, defense=3, moves=shell_moves)

    return ember, shell


def main():
    pygame.init()
    screen = pygame.display.set_mode(RESOLUTION)
    pygame.display.set_caption('Creature Battle')
    clock = pygame.time.Clock()

    assets = load_assets()
    ui = UI(assets, screen)

    player, enemy = create_player_and_enemy()
    bm = BattleManager(player, enemy)

    selected_move = 0

    running = True
    print('[EVENT] GAME START')

    while running:
        dt = clock.tick(FPS) / 1000.0

        for ev in pygame.event.get():
            if ev.type == QUIT:
                running = False
            elif ev.type == KEYDOWN:
                if ev.key == K_ESCAPE:
                    running = False
                elif ev.key == K_UP:
                    if bm.is_input_allowed():
                        selected_move = (selected_move - 1) % len(bm.player.moves)
                elif ev.key == K_DOWN:
                    if bm.is_input_allowed():
                        selected_move = (selected_move + 1) % len(bm.player.moves)
                elif ev.key in (K_RETURN, K_KP_ENTER):
                    if bm.is_input_allowed():
                        bm.player_use_move(selected_move)
                elif ev.key == K_r:
                    # Only reset after terminal states per Plan requirement
                    if bm.state in ('win', 'lose'):
                        bm.reset()
                        selected_move = 0

        # Update battle manager (message timing and state transitions)
        bm.update(dt)

        # Draw everything
        ui.draw(bm, selected_move)
        pygame.display.flip()

    pygame.quit()


if __name__ == '__main__':
    main()
