import pygame

class UI:
    def __init__(self, font_size=24):
        self.font = pygame.font.Font(None, font_size)

    def draw(self, surface, score: int, lives: int, controls_text: str):
        # draw score and lives at top
        score_surf = self.font.render(f"Score: {score}", True, (255, 255, 255))
        lives_surf = self.font.render(f"Lives: {lives}", True, (255, 255, 255))
        controls_surf = self.font.render(controls_text, True, (255, 255, 255))
        surface.blit(score_surf, (10, 10))
        surface.blit(lives_surf, (10, 40))
        surface.blit(controls_surf, (10, 70))
