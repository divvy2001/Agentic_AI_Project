import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
from pathlib import Path
from typing import Optional

from game import constants as C
from game.player import Player
from game.alien import AlienGrid


def main():
    pygame.init()
    screen = pygame.display.set_mode((C.SCREEN_WIDTH, C.SCREEN_HEIGHT))
    pygame.display.set_caption("Space Invaders")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, C.HUD_FONT_SIZE)
    big_font = pygame.font.Font(None, 64)

    # Game state
    score = 0
    lives = C.PLAYER_START_LIVES
    game_state = "playing"  # 'playing', 'win', 'lose'

    # Track last printed event state to avoid duplicate [EVENT] lines
    last_printed_score = score
    last_printed_lives = lives
    last_printed_state: Optional[str] = None

    # Create player and aliens
    player_start_x = C.SCREEN_WIDTH // 2
    player_start_y = C.SCREEN_HEIGHT - 50
    player = Player(player_start_x, player_start_y)
    aliens = AlienGrid()

    def reset_game():
        nonlocal score, lives, game_state, last_printed_score, last_printed_lives, last_printed_state, player, aliens
        score = 0
        lives = C.PLAYER_START_LIVES
        game_state = "playing"
        last_printed_score = score
        last_printed_lives = lives
        last_printed_state = None
        player.reset(player_start_x, player_start_y)
        aliens.reset()

    running = True

    while running:
        dt = clock.tick(C.FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    reset_game()
                elif game_state == "playing":
                    if event.key == pygame.K_SPACE:
                        created = player.shoot()
                        if created:
                            # created a bullet; nothing else to print here
                            pass

        keys = pygame.key.get_pressed()
        # Movement only when playing
        if game_state == "playing":
            move_dx = 0
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                move_dx -= C.PLAYER_SPEED * dt
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                move_dx += C.PLAYER_SPEED * dt
            if move_dx:
                player.move(move_dx)

        # Updates
        if game_state == "playing":
            player.update(dt)
            aliens.update(dt)

            # Check player's bullet vs aliens
            pb = player.get_bullet()
            if pb:
                hit = aliens.check_collision(pb)
                if hit:
                    score += C.ALIEN_SCORE
                    player.bullet = None
                    if score != last_printed_score:
                        print(f"[EVENT] SCORE:{score}")
                        last_printed_score = score

            # Check alien bullets vs player
            for b in list(aliens.bullets):
                if b.colliderect(player.rect):
                    aliens.bullets.remove(b)
                    lives -= 1
                    if lives != last_printed_lives:
                        print(f"[EVENT] LIVES:{lives}")
                        last_printed_lives = lives

            # Check lose by alien reaching player row
            if aliens.any_reached(player.rect.top):
                game_state = "lose"
                if last_printed_state != "lose":
                    print("[EVENT] LOSE")
                    last_printed_state = "lose"

            # Check lose by lives
            if lives <= 0 and game_state == "playing":
                game_state = "lose"
                if last_printed_state != "lose":
                    print("[EVENT] LOSE")
                    last_printed_state = "lose"

            # Check win
            if aliens.is_empty() and game_state == "playing":
                game_state = "win"
                if last_printed_state != "win":
                    print("[EVENT] WIN")
                    last_printed_state = "win"

        # Draw
        screen.fill(C.BLACK)

        # HUD background
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, C.SCREEN_WIDTH, C.HUD_HEIGHT))
        hud_score = font.render(f"Score: {score}", True, C.WHITE)
        hud_lives = font.render(f"Lives: {lives}", True, C.WHITE)
        hud_controls = font.render(C.CONTROLS_TEXT, True, C.WHITE)
        screen.blit(hud_score, (8, 8))
        screen.blit(hud_lives, (200, 8))
        screen.blit(hud_controls, (360, 8))

        # Draw game objects
        aliens.draw(screen)
        player.draw(screen)

        # Win/Lose overlay
        if game_state == "win":
            text = big_font.render("WIN", True, C.YELLOW)
            rect = text.get_rect(center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2))
            screen.blit(text, rect)
        elif game_state == "lose":
            text = big_font.render("LOSE", True, C.RED)
            rect = text.get_rect(center=(C.SCREEN_WIDTH // 2, C.SCREEN_HEIGHT // 2))
            screen.blit(text, rect)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
