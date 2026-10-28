# Crumb Chase (pygame)

## Spec

Create a small one-screen maze game called "Crumb Chase". The player is a little green mouse in a simple grid maze of 15 by 15 tiles with walls. The arrow keys turn the mouse up, down, left or right, and it keeps moving tile by tile in that direction until it hits a wall. Every open tile starts with a small cheese crumb; eating a crumb adds 10 points. Two cats wander the maze; each cat moves one tile at a time and at each junction picks a direction toward the mouse. If a cat touches the mouse, the mouse loses a life and everyone returns to their start tiles. The mouse has 3 lives. Eating every crumb wins the game; losing all lives ends the game. Show the score and lives at the top of the window. When the game is won or over, show WIN or GAME OVER with the final score and freeze the game. Press R to restart with 3 lives and score 0, and Escape to quit. Print a line to the console every time a control takes effect: TURN UP, TURN DOWN, TURN LEFT, TURN RIGHT, RESTART and QUIT, and print WIN or GAME OVER when the game ends. Use plain coloured shapes only; no images or sounds. Keep it to as few files as possible.

## Notes

- Expected engine: pygame
- Maze chase in the style of classic maze games; original mouse and cats.
- Only the text under "## Spec" is sent to the Planner. This Notes section is ignored.
