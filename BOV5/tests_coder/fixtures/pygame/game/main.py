"""Minimal real Pygame game. SPACE calls the same GameState used by fixtures."""
import os
import pygame
from game.state import GameState


def main():
    pygame.init()
    screen = pygame.display.set_mode((640, 480))
    clock = pygame.time.Clock()
    game = GameState()
    running = True
    frames = 0
    limit = int(os.environ.get("CODER_SMOKE_FRAMES", "0"))
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                game.award_point()
                print(f"[EVENT] score_changed value={game.score}", flush=True)
                if game.phase == "WIN":
                    print("[EVENT] win", flush=True)
        screen.fill((35, 42, 60))
        pygame.display.flip()
        frames += 1
        if limit and frames >= limit:
            running = False
        clock.tick(30)
    pygame.quit()


if __name__ == "__main__":
    main()
