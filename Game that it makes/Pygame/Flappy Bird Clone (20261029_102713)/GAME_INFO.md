# Flappy Bird Clone

- Engine: pygame
- Built: run 20261029_102713
- Result: DONE: 2 passed, 1 failed (triage disabled)
- Spec file: flappybird_prim.md
- Play: double-click `play.bat`

## Spec

Create a one-screen side-scrolling game called "Flappy Bird Clone". A small bird stays at a fixed horizontal position near the left of the window and falls downward under constant gravity. Pressing Space gives the bird an upward flap, a single instant upward burst of velocity; releasing Space does nothing. Pipes with a gap in the middle scroll in from the right edge of the screen toward the left at a constant speed, with a new pipe appearing at a regular time interval and a new random gap height each time. Passing through a pipe's gap without touching a pipe adds 1 point. Touching any pipe, or the bird touching the top or bottom edge of the screen, ends the game. Generate exactly two small image assets: the bird and a single pipe segment. Use a plain sky-blue background colour instead of a background image. Show the current score in the top-left corner at all times. When the game is over, show GAME OVER and the final score, and stop moving the pipes and the bird. Press R to restart with score 0, the bird back at its starting position, and all pipes cleared. Press Escape to quit. Print a line to the console every time a control takes effect: FLAP, RESTART and QUIT, and print GAME OVER when the game ends. No sounds. Keep it to as few files as possible.
