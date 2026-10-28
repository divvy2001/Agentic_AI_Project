"""CLI score game: intentionally contains one off-by-one bug for Repair testing."""
import sys


def run_game(stdin, stdout):
    score = 0
    for line in stdin:
        action = line.strip()
        if action == "q":
            break
        if action == "1":
            score += 1
            # BUG: at score=3 this should be WIN, but is still ONGOING.
            status = "WIN" if score > 3 else "ONGOING"
            print(f"SCORE:{score} STATUS:{status}", file=stdout, flush=True)
    return score


if __name__ == "__main__":
    run_game(sys.stdin, sys.stdout)
