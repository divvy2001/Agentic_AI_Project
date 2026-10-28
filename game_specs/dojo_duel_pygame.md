# Dojo Duel (pygame)

## Spec

Create a tiny one-screen 2D fighting game called "Dojo Duel". The player controls a red-belt martial artist on the left; a blue-belt rival controlled by the computer stands on the right. Generate exactly two small image assets: the red-belt fighter and the blue-belt fighter, both facing sideways. Use a plain wooden-brown floor and a light background colour instead of a background image. Both fighters stand on the floor with simple gravity. The Left and Right arrow keys walk the player, the Up arrow jumps, and Space throws a punch. A punch that lands pushes the opponent back a short fixed distance, makes it flash white briefly, and removes 10 health. The rival walks toward the player and punches when close, with a one-second pause between punches. Each fighter has 100 health shown as a bar at the top of the screen. When a fighter reaches 0 health, show WIN or GAME OVER and freeze the game. Press R to restart the fight and Escape to quit. Print a line to the console every time a control takes effect: MOVE LEFT, MOVE RIGHT, JUMP, PUNCH, RESTART and QUIT, and print WIN or GAME OVER when the fight ends. No sounds. Keep the code simple and in as few files as possible.

## Notes

- Expected engine: pygame
- Same fighting game, simple gravity and fixed knockback so the planner picks pygame. Compare with the Godot version.
- Only the text under "## Spec" is sent to the Planner. This Notes section is ignored.
