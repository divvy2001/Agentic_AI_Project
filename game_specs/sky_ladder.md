# Sky Ladder

## Spec

Create a side-scrolling platformer called "Sky Ladder" with 3 short levels. The player is a small orange square; Left and Right arrow keys move it and Space jumps, with simple gravity. Each level is about three screens wide, made of solid grey platforms and gaps; the camera follows the player horizontally. Blue coins give 10 points each. Purple slimes walk back and forth on platforms; touching one from the side loses a life, landing on top removes it. Falling into a gap loses a life and returns the player to the start of the level. The player has 3 lives. A green door at the end of each level moves to the next level; finishing level 3 shows WIN; losing all lives shows GAME OVER; both freeze the game. Show score, lives and level number at the top. Press R to restart from level 1 and Escape to quit. Print a line to the console every time a control takes effect: MOVE LEFT, MOVE RIGHT, JUMP, RESTART and QUIT, and print WIN or GAME OVER when the game ends. Use plain coloured shapes only; no images or sounds. Keep the code simple and in as few files as possible.

## Notes

- Expected engine: pygame
- Level 4 of the pygame ladder: scrolling platformer, 3 levels. May need CODER_MAX_STEPS=120.
- Only the text under "## Spec" is sent to the Planner. This Notes section is ignored.
