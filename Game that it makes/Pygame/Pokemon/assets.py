import pygame
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent / "assets"


def load_assets():
    """Load and return a dict of surfaces: 'bg', 'ember', 'shell'.
    Uses images shipped in game/assets/ as listed by the Plan.
    """
    assets = {}
    try:
        assets['bg'] = pygame.image.load(str(ASSET_DIR / 'grassy_background.png')).convert()
    except Exception:
        # Fallback: procedural background if asset missing
        surf = pygame.Surface((320, 180))
        surf.fill((100, 200, 100))
        assets['bg'] = surf

    try:
        assets['ember'] = pygame.image.load(str(ASSET_DIR / 'emberkit_sprite.png')).convert_alpha()
    except Exception:
        # Procedural placeholder: orange square
        s = pygame.Surface((64, 64), pygame.SRCALPHA)
        s.fill((255, 120, 0))
        assets['ember'] = s

    try:
        assets['shell'] = pygame.image.load(str(ASSET_DIR / 'shellwave_sprite.png')).convert_alpha()
    except Exception:
        s = pygame.Surface((64, 64), pygame.SRCALPHA)
        s.fill((0, 120, 255))
        assets['shell'] = s

    return assets
