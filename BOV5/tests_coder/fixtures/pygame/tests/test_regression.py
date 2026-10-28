import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from game.state import GameState
state = GameState()
for _ in range(2):
    state.award_point()
assert state.score == 2
assert state.phase == "PLAYING", f"score={state.score} phase={state.phase}"
