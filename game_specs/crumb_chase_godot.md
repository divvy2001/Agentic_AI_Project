# Crumb Chase (Godot)

## Spec

Create a small one-screen maze game called "Crumb Chase". The player is a little green mouse in a 15 by 15 tile maze with walls; the mouse starts in an open corridor where it can move in all four directions. The arrow keys turn the mouse up, down, left or right, and it glides smoothly from tile to tile in that direction with a squash-and-stretch animation until it hits a wall. Every open tile starts with a small cheese crumb; eating a crumb adds 10 points and pops it with a little sparkle particle burst. Two cats chase the mouse through the maze, sliding smoothly between tiles and choosing the direction toward the mouse at each junction. If a cat touches the mouse, the mouse loses a life with a short spin-and-fade animation and everyone returns to their start tiles. The mouse has 3 lives. A level designer should be able to redraw the maze walls visually as a tile map and preview the level without touching code. Eating every crumb wins the game; losing all lives ends the game. Show the score and lives at the top of the window. When the game is won or over, show WIN or GAME OVER with the final score and freeze the game. Press R to restart with 3 lives and score 0, and Escape to quit. Print a line to the console every time a control takes effect: TURN UP, TURN DOWN, TURN LEFT, TURN RIGHT, RESTART and QUIT, and print WIN or GAME OVER when the game ends. Use plain coloured shapes only; no images or sounds.

## Notes

- Expected engine: godot
- Same maze game; animations, particles and a visual tile map point to Godot. Large build: hit the 80-step limit once.
- Only the text under "## Spec" is sent to the Planner. This Notes section is ignored.
