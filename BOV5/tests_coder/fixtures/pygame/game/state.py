"""Actual score-state logic imported by the Pygame runtime; contains one bug."""
class GameState:
    def __init__(self):
        self.score = 0
        self.phase = "PLAYING"

    def award_point(self):
        self.score += 1
        # BUG: should trigger WIN at exactly 3.
        if self.score > 3:
            self.phase = "WIN"
