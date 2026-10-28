# Moon Hopper

## Spec

Create a tiny one-screen game called "Moon Hopper". The player flies a small lander that starts hovering near the top of the screen above a flat landing pad. Gravity constantly pulls the lander down. Holding the Up arrow fires the thruster and pushes the lander in the direction it is facing; the Left and Right arrow keys rotate it. The lander has real physics: it keeps its momentum and drifts, and it bounces off the left and right screen edges. Touching down on the pad slowly and upright wins; hitting the ground too fast or tilted crashes. Show the current speed in the top-left corner, and show a small flame shape behind the lander while thrusting. When the player wins or crashes, show WIN or GAME OVER and freeze the game. Press R to restart from the top and Escape to quit. Print a line to the console every time a control takes effect: THRUST, ROTATE LEFT, ROTATE RIGHT, RESTART and QUIT, and print WIN or GAME OVER when the game ends. Use plain coloured shapes only; no images or sounds. Keep it to one scene and as few scripts as possible.

## Notes

- Expected engine: godot
- Cheap Godot test: gravity, thrust, rotation, momentum.
- Only the text under "## Spec" is sent to the Planner. This Notes section is ignored.
