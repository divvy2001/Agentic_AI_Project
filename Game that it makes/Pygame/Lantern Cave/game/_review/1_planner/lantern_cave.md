# Lantern Cave

## Spec

Create a small text adventure game played in the terminal called "Lantern Cave". The player explores five connected locations: a forest clearing, a cave entrance, a dark tunnel, an underground lake and a treasure room. The player types one command per line: look, go north, go south, go east, go west, take <item>, inventory, help and quit. The cave entrance holds a lantern and the underground lake holds a rusty key. The dark tunnel cannot be crossed without the lantern, and the treasure room is locked until the player has the rusty key. Reaching the treasure room with the key wins the game. Every command prints one fixed confirmation line first, then a short description: look prints LOOK, a successful move prints MOVED NORTH, MOVED SOUTH, MOVED EAST or MOVED WEST, a blocked move prints BLOCKED, take prints TOOK followed by the item name, inventory prints INVENTORY, help prints HELP, and quit prints QUIT and exits. An unknown command prints UNKNOWN COMMAND and does not change anything. Winning prints WIN and ends the game. Show the player's current location after every command. Use the standard library only and keep it in as few files as possible.

## Notes

- Expected engine: terminal (text game, no window)
- Cheapest kind of test: no images, no graphics; the Tester types commands into the game instead of pressing keys
- Controls = typed commands: look, go north/south/east/west, take, inventory, help, quit
- The start location must allow at least one move so the "go" tests can succeed
- Only the text under "## Spec" is sent to the Planner. This Notes section is ignored.
