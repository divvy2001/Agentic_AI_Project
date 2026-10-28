from coder_agent_adhoc.adapters._python import observation

PLAYBOOK = """TERMINAL PLAYBOOK
- Python entry exactly as planned; standard library only unless the Plan lists dependencies.
- Line-based stdin/stdout protocol: print a prompt or state line, read one line, apply it,
  print the resulting state. flush=True on prints. Invalid input must not advance the turn.
- If the Plan requires physical arrow keys or immediate key presses, ALSO implement real
  interactive console input when sys.stdin.isatty() is true. On Windows use standard-library
  msvcrt.getwch(); decode the special '\\x00'/'\\xe0' prefix plus its next keycode (H/P/K/M for
  up/down/left/right). Normal letters map to the planned controls. Keep newline commands
  and EOF handling for redirected/non-interactive stdin; do not call getwch in that mode.
  Typing the word 'up' is not implementation of a physical arrow key. Describe both input
  modes accurately. Do not use os.system('cls'), subprocesses, external input packages or
  test-only flags; scrolling output or ANSI stdout is sufficient.
- Handle EOF (input() raising EOFError / empty readline) and the quit command by exiting
  cleanly with code 0. Print explicit state lines (e.g. SCORE:X, WIN, LOSE) only when the
  real game state changes.
- test_input_example may be prose. The startup check sends stdin only when the example is an
  explicit newline-separated sequence; otherwise it verifies the game reaches its first input.
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
    if observed.get('game_lines', 0) < 3:
        return 'update_path_not_observed'
    if p['architecture']['requires_input'] and observed.get('inputs', 0) < 1:
        return 'update_path_not_observed'
    return None
