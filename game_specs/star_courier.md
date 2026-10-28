# Star Courier

## Spec

Create a one-screen top-down space shooter called "Star Courier". The player flies a small green ship at the bottom of the screen; the arrow keys move it in all four directions and it stays inside the screen. Space fires a short yellow laser upward, at most one shot every quarter second. Waves of red rock shapes fall from the top at different speeds; each wave has more rocks than the last. A laser that hits a rock destroys it and adds 10 points; a rock that touches the ship removes one of 3 shields. Show the score, wave number and shields at the top of the screen. Losing all shields shows GAME OVER and freezes the game. Press R to restart and Escape to quit. Print a line to the console every time a control takes effect: MOVE UP, MOVE DOWN, MOVE LEFT, MOVE RIGHT, SHOOT, RESTART and QUIT, and print GAME OVER when the game ends. Use plain coloured shapes only; no images or sounds. Keep the code simple and in as few files as possible.

## Notes

- Expected engine: pygame
- Level 1 of the pygame ladder: many moving objects, waves, bullets.
- Only the text under "## Spec" is sent to the Planner. This Notes section is ignored.
