#!/usr/bin/env python3
"""Tic Tac Toe

Terminal-based two-player Tic Tac Toe game matching the Planner requirements.
All state is owned in this module. Run as `python game/tic_tac_toe.py`.
"""
import sys
import os

# Ensure running module works both as script and as package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Game state (module-owned)
board = []  # list[str] of length 9, either '1'..'9' or 'X'/'O'
current_player = 'X'  # 'X' starts (Player 1)
game_over = False
winner = None  # 'X' or 'O' or None
moves_made = 0

WIN_COMBINATIONS = [
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
]


def print_title() -> None:
    """Print the game title."""
    print("Tic Tac Toe", flush=True)


def print_board(b: list) -> None:
    """Print the 3x3 board to stdout. Cells show numbers or X/O.

    Layout example:
     1 | 2 | 3
    ---+---+---
     4 | 5 | 6
    ---+---+---
     7 | 8 | 9
    """
    # Use explicit formatting so lines are predictable for tests.
    print("", flush=True)
    for i in range(0, 9, 3):
        row = " | ".join(b[i:i+3])
        print(" " + row, flush=True)
        if i < 6:
            print("---+---+---", flush=True)
    print("", flush=True)


def check_winner(b: list) -> str:
    """Return 'X' or 'O' if there is a winner on board b, else return None.

    b: list of 9 strings
    """
    for a, c, d in WIN_COMBINATIONS:
        if b[a] == b[c] == b[d] and b[a] in ("X", "O"):
            return b[a]
    return None


def reset_game() -> None:
    """Reset the global game state to start a fresh game."""
    global board, current_player, game_over, winner, moves_made
    board = [str(i + 1) for i in range(9)]
    current_player = 'X'
    game_over = False
    winner = None
    moves_made = 0


def handle_move(cell_number: int) -> None:
    """Attempt to place current_player's mark at cell_number (1-9).

    On success, prints MOVE line and the board, and updates game state (moves, check winner).
    On invalid (occupied), prints message and does not change turn.
    """
    global board, current_player, game_over, winner, moves_made
    idx = cell_number - 1
    if board[idx] in ('X', 'O'):
        print("Invalid move, cell already taken. Please try again.", flush=True)
        return
    # Place mark
    board[idx] = current_player
    moves_made += 1
    print(f"MOVE {current_player} {cell_number}", flush=True)
    print_board(board)
    # Check winner
    w = check_winner(board)
    if w:
        winner = w
        game_over = True
        if winner == 'X':
            print("WIN Player 1", flush=True)
        else:
            print("WIN Player 2", flush=True)
        return
    if moves_made >= 9:
        game_over = True
        print("DRAW", flush=True)
        return
    # Toggle player
    current_player = 'O' if current_player == 'X' else 'X'


def main() -> None:
    """Main input loop. Reads lines from stdin and updates game state.

    Accepted inputs:
    - '1'..'9' to place mark
    - 'R' or 'r' to reset after a finished game (or at any time to restart)
    - 'Q' or 'q' to quit

    On EOF, exits cleanly with code 0.
    """
    reset_game()
    print_title()
    print_board(board)

    # Prompt loop
    while True:
        try:
            line = input().strip()
        except EOFError:
            # Clean exit on EOF
            sys.exit(0)

        if line == "":
            # Ignore empty lines
            continue

        cmd = line.strip()
        # Global quit anytime
        if cmd.lower() == 'q':
            sys.exit(0)

        # Reset anytime when requested
        if cmd.lower() == 'r':
            reset_game()
            print_title()
            print_board(board)
            continue

        if not game_over:
            # Expect a number 1-9
            if cmd.isdigit():
                try:
                    n = int(cmd)
                except ValueError:
                    print("Invalid input. Please enter a number from 1 to 9.", flush=True)
                    continue
                if 1 <= n <= 9:
                    handle_move(n)
                else:
                    print("Invalid input. Please enter a number from 1 to 9.", flush=True)
                continue
            else:
                print("Invalid input. Please enter a number from 1 to 9.", flush=True)
                continue
        else:
            # Game is over; only R or Q are meaningful
            if cmd.lower() == 'r':
                reset_game()
                print_title()
                print_board(board)
                continue
            else:
                print("Game over. Press R to play again or Q to quit.", flush=True)
                continue


if __name__ == '__main__':
    main()
