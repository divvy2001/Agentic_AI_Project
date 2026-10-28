from coder_agent_adhoc.adapters._python import observation

PLAYBOOK = """PYGAME PLAYBOOK
- Real pygame.init(), display.set_mode(Planner resolution), clock.tick(Planner fps) and a
  loop of: handle events -> update state -> draw -> pygame.display.flip(). Quit on QUIT and
  Escape when the Plan asks for it.
- Background: every frame first fill the WHOLE window (screen.fill) and, if there is a background
  image, scale it to the window size with pygame.transform.scale(img, screen.get_size()). Never draw
  a background at a hard-coded size smaller than the Planner resolution.
- Never exit early for headless/smoke runs and never read test-only environment flags. The
  harness stops the game itself after several presented frames under SDL dummy drivers.
- Fonts: pygame.font.Font(None, size). Do not use SysFont or system font paths.
- Load assets relative to the source file: Path(__file__).resolve().parent / 'assets' / name.
  Use only assets listed by list_assets; procedural shapes otherwise.
- Movement scaled by dt or fixed per frame consistently; collisions with pygame.Rect.
  For grid/turn-based Plans use one cell/action per KEYDOWN and no continuous held movement.
  Discrete actions (jump, select, restart) on KEYDOWN/MOUSEBUTTONDOWN; continuous movement may
  use key.get_pressed(). Keep game state in plain attributes so it can be inspected, and print
  [EVENT] lines (e.g. [EVENT] SCORE:2, [EVENT] WIN) only on real state changes.
  For EVERY control the game handles, print one console line with flush=True when it takes
  effect (e.g. DIRECTION up, RESTART, QUIT, PAUSE), plus GAME OVER / WIN / SCORE:<n> on those
  events. List each control and its exact printed line in the play manual.
- Restart must rebuild every object, counter, timer and velocity; after WIN/LOSE freeze play
  until restart.
- If the entry imports sibling modules, put
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))) before those imports so both
  `python game/main.py` and `python -m game.main` work."""


def playbook(p):
    return PLAYBOOK


def contract_check(p):
    return None


def source_check(p):
    return None


def boot_check(p, result):
    observed = observation(result)
    if (observed.get('game_lines', 0) < 3 or observed.get('frames', 0) < 3
            or observed.get('loop_cycles', 0) < 2):
        return 'update_path_not_observed'
    from coder_agent_adhoc.presentation import expected
    if expected(p) and 'pixel_colors' in observed and observed['pixel_colors'] < 2:
        return 'presentation_uniform_frame'
    return None
