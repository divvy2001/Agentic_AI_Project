import sys
import os
# Ensure sibling imports work when running as a module or script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
import random
from typing import List, Optional, Tuple

# Game constants from the Plan
WIDTH = 400
HEIGHT = 600
FPS = 60
COLS = 10
ROWS = 20
CELL_PADDING = 1  # padding between cells when drawing
TOP_MARGIN = 40  # space at top for score display

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (50, 50, 50)

# Piece colors (one color per shape)
COLOR_SQUARE = (200, 100, 100)
COLOR_LINE = (100, 200, 100)
COLOR_L = (100, 100, 200)
COLOR_T = (200, 200, 100)

# Fall timing (seconds per row)
FALL_INTERVAL = 0.5

class TetrisGame:
    """Main Tetris game class.

    State owned here:
      - cols, rows, grid: the playfield grid as grid[row][col] = Optional[color]
      - score: integer
      - current_piece: dict with keys matrix, x, y, color
      - game_over: bool
      - fall_timer: float
    """

    def __init__(self, width: int = WIDTH, height: int = HEIGHT,
                 cols: int = COLS, rows: int = ROWS):
        pygame.init()
        self.width = width
        self.height = height
        self.cols = cols
        self.rows = rows
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Simple Tetris")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)

        self.cell_size = min(self.width // self.cols, (self.height - TOP_MARGIN) // self.rows)
        self.grid_origin_x = (self.width - self.cell_size * self.cols) // 2
        self.grid_origin_y = TOP_MARGIN

        self.grid: List[List[Optional[Tuple[int,int,int]]]] = []
        self.score = 0
        self.current_piece = None
        self.game_over = False
        self.fall_timer = 0.0

        # Define the four shapes: matrices using 1 for filled cells
        self.pieces = [
            {"name": "square", "matrix": [[1,1],[1,1]], "color": COLOR_SQUARE},
            {"name": "line", "matrix": [[1,1,1,1]], "color": COLOR_LINE},
            {"name": "L", "matrix": [[1,0],[1,0],[1,1]], "color": COLOR_L},
            {"name": "T", "matrix": [[1,1,1],[0,1,0]], "color": COLOR_T},
        ]

        self.reset_game()

    def reset_game(self) -> None:
        """Reset the entire game: clear grid, reset score, spawn first piece."""
        self.grid = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        self.score = 0
        self.current_piece = None
        self.game_over = False
        self.fall_timer = 0.0
        self.spawn_piece()
        print("RESTART", flush=True)
        print(f"SCORE:{self.score}", flush=True)

    def spawn_piece(self) -> None:
        piece_def = random.choice(self.pieces)
        matrix = [row[:] for row in piece_def["matrix"]]
        color = piece_def["color"]

        px = (self.cols - len(matrix[0])) // 2
        py = 0
        self.current_piece = {"matrix": matrix, "x": px, "y": py, "color": color, "name": piece_def["name"]}

        # If it immediately overlaps locked blocks -> game over
        if not self.can_place(matrix, px, py):
            self.game_over = True
            print("GAME OVER", flush=True)

    def can_place(self, matrix: List[List[int]], x: int, y: int) -> bool:
        """Return True if the given matrix can be placed at grid position (x,y) without collisions or out-of-bounds."""
        for r, row in enumerate(matrix):
            for c, cell in enumerate(row):
                if cell:
                    gx = x + c
                    gy = y + r
                    if gx < 0 or gx >= self.cols or gy < 0 or gy >= self.rows:
                        return False
                    if self.grid[gy][gx] is not None:
                        return False
        return True

    def rotate_matrix(self, matrix: List[List[int]]) -> List[List[int]]:
        # Rotate clockwise: transpose and reverse rows
        return [list(row) for row in zip(*matrix[::-1])]

    def lock_piece(self) -> None:
        if not self.current_piece:
            return
        mat = self.current_piece["matrix"]
        x = self.current_piece["x"]
        y = self.current_piece["y"]
        color = self.current_piece["color"]
        for r, row in enumerate(mat):
            for c, cell in enumerate(row):
                if cell:
                    gx = x + c
                    gy = y + r
                    if 0 <= gy < self.rows and 0 <= gx < self.cols:
                        self.grid[gy][gx] = color
        # After locking, clear lines
        cleared = self.clear_lines()
        if cleared > 0:
            self.score += 100 * cleared
            print(f"SCORE:{self.score}", flush=True)
        # Spawn next piece unless game over detected on spawn
        self.spawn_piece()

    def clear_lines(self) -> int:
        cleared = 0
        new_rows = []
        for row in self.grid:
            if all(cell is not None for cell in row):
                cleared += 1
            else:
                new_rows.append(row)
        for _ in range(cleared):
            new_rows.insert(0, [None for _ in range(self.cols)])
        if cleared > 0:
            self.grid = new_rows
        return cleared

    def move_current(self, dx: int, dy: int) -> bool:
        if not self.current_piece or self.game_over:
            return False
        new_x = self.current_piece["x"] + dx
        new_y = self.current_piece["y"] + dy
        if self.can_place(self.current_piece["matrix"], new_x, new_y):
            self.current_piece["x"] = new_x
            self.current_piece["y"] = new_y
            return True
        return False

    def rotate_current(self) -> bool:
        if not self.current_piece or self.game_over:
            return False
        new_mat = self.rotate_matrix(self.current_piece["matrix"])
        if self.can_place(new_mat, self.current_piece["x"], self.current_piece["y"]):
            self.current_piece["matrix"] = new_mat
            return True
        return False

    def update(self, dt: float) -> None:
        if self.game_over:
            return
        self.fall_timer += dt
        if self.fall_timer >= FALL_INTERVAL:
            self.fall_timer -= FALL_INTERVAL
            # Try to move down; if can't, lock
            if not self.move_current(0, 1):
                # Lock in place
                self.lock_piece()

    def handle_keydown(self, key) -> None:
        if key == pygame.K_LEFT:
            moved = self.move_current(-1, 0)
            if moved:
                print("MOVE LEFT", flush=True)
        elif key == pygame.K_RIGHT:
            moved = self.move_current(1, 0)
            if moved:
                print("MOVE RIGHT", flush=True)
        elif key == pygame.K_DOWN:
            # Soft drop: move down one row immediately; if can't, lock
            if self.game_over:
                return
            moved = self.move_current(0, 1)
            if moved:
                print("SOFT DROP", flush=True)
            else:
                # Lock immediately if cannot move down
                self.lock_piece()
        elif key == pygame.K_UP:
            rotated = self.rotate_current()
            if rotated:
                print("ROTATE", flush=True)
        elif key == pygame.K_r:
            self.reset_game()
        elif key == pygame.K_ESCAPE:
            print("QUIT", flush=True)
            pygame.quit()
            sys.exit(0)

    def draw(self) -> None:
        # Clear background
        self.screen.fill(BLACK)

        # Draw grid background rectangle
        grid_w = self.cell_size * self.cols
        grid_h = self.cell_size * self.rows
        pygame.draw.rect(self.screen, GRAY, (self.grid_origin_x - 2, self.grid_origin_y - 2, grid_w + 4, grid_h + 4))

        # Draw locked blocks
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.grid[r][c]
                if cell is not None:
                    self.draw_cell(c, r, cell)
                else:
                    # empty cell background
                    self.draw_cell_rect(c, r, BLACK)

        # Draw current piece
        if self.current_piece and not self.game_over:
            mat = self.current_piece["matrix"]
            color = self.current_piece["color"]
            for r, row in enumerate(mat):
                for c, cell in enumerate(row):
                    if cell:
                        gx = self.current_piece["x"] + c
                        gy = self.current_piece["y"] + r
                        if 0 <= gx < self.cols and 0 <= gy < self.rows:
                            self.draw_cell(gx, gy, color)

        # Draw grid lines (optional subtle lines)
        for r in range(self.rows + 1):
            y = self.grid_origin_y + r * self.cell_size
            pygame.draw.line(self.screen, BLACK, (self.grid_origin_x, y), (self.grid_origin_x + grid_w, y))
        for c in range(self.cols + 1):
            x = self.grid_origin_x + c * self.cell_size
            pygame.draw.line(self.screen, BLACK, (x, self.grid_origin_y), (x, self.grid_origin_y + grid_h))

        # Draw score in top-right corner
        score_surf = self.font.render(f"Score: {self.score}", True, WHITE)
        score_pos = score_surf.get_rect(topright=(self.width - 10, 10))
        self.screen.blit(score_surf, score_pos)

        # If game over, overlay message
        if self.game_over:
            over_surf = self.font.render("GAME OVER", True, WHITE)
            over_rect = over_surf.get_rect(center=(self.width // 2, 20))
            self.screen.blit(over_surf, over_rect)
            final_surf = self.font.render(f"Final Score: {self.score}", True, WHITE)
            final_rect = final_surf.get_rect(center=(self.width // 2, 40))
            self.screen.blit(final_surf, final_rect)

        pygame.display.flip()

    def draw_cell(self, grid_x: int, grid_y: int, color: Tuple[int,int,int]) -> None:
        x = self.grid_origin_x + grid_x * self.cell_size + CELL_PADDING
        y = self.grid_origin_y + grid_y * self.cell_size + CELL_PADDING
        size = self.cell_size - CELL_PADDING * 2
        pygame.draw.rect(self.screen, color, (x, y, size, size))

    def draw_cell_rect(self, grid_x: int, grid_y: int, color: Tuple[int,int,int]) -> None:
        x = self.grid_origin_x + grid_x * self.cell_size + CELL_PADDING
        y = self.grid_origin_y + grid_y * self.cell_size + CELL_PADDING
        size = self.cell_size - CELL_PADDING * 2
        pygame.draw.rect(self.screen, color, (x, y, size, size))

    def run(self) -> None:
        # Main loop
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("QUIT", flush=True)
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.KEYDOWN:
                    self.handle_keydown(event.key)

            # Update game state
            self.update(dt)

            # Draw
            self.draw()


if __name__ == "__main__":
    game = TetrisGame()
    game.run()
