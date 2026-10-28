# Dungeon Delve

## Spec

Create a small turn-based dungeon game called "Dungeon Delve" on a 20 by 15 tile grid. Each floor is a randomly generated set of rectangular rooms joined by corridors, with walls between them. The player is a white square; each arrow key press moves one tile, and every player move is one turn. Red goblins move one tile toward the player each turn once they can see the player; walking into a goblin attacks it. The player has 10 health and each goblin has 3; an attack does 1 damage. Yellow potions on the floor restore 3 health when walked over. A green staircase leads to the next floor. Reaching the bottom of floor 3 shows WIN; reaching 0 health shows GAME OVER; both freeze the game. Show health and floor number at the top. Press R to restart from floor 1 and Escape to quit. Print a line to the console every time a control takes effect: MOVE UP, MOVE DOWN, MOVE LEFT, MOVE RIGHT, RESTART and QUIT, and print WIN or GAME OVER when the game ends. Use plain coloured squares only; no images or sounds. Keep the code simple and in as few files as possible.

## Notes

- Expected engine: pygame
- Level 3 of the pygame ladder: turn-based roguelike, random rooms. May need CODER_MAX_STEPS=120.
- Only the text under "## Spec" is sent to the Planner. This Notes section is ignored.
