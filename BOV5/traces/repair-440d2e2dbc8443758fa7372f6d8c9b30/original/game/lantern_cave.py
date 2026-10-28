import sys
from typing import Dict, List, Optional

# Ensure imports work when executed as a module or script
sys.path.insert(0, sys.path[0])

class Game:
    """Lantern Cave text adventure.

    State owned by Game:
    - map: Dict[str, Dict[str, str]] mapping location -> {direction: destination}
    - descriptions: Dict[str, str] short descriptions for look and movement
    - items_at: Dict[str, List[str]] items present in each location
    - current_location: str
    - inventory: List[str]

    Public methods:
    - parse_and_execute(command: str) -> bool: process one command, print outputs, return False to exit.
    - run() -> None: interactive loop until parse_and_execute returns False or EOF.
    """

    def __init__(self) -> None:
        # Map connectivity
        self.map: Dict[str, Dict[str, str]] = {
            "clearing": {"east": "cave", "south": "tunnel"},
            "cave": {"west": "clearing"},
            "tunnel": {"north": "clearing", "south": "lake"},
            "lake": {"north": "tunnel", "east": "treasure"},
            "treasure": {"west": "lake"},
        }

        # Short descriptions for look
        self.descriptions: Dict[str, str] = {
            "clearing": "You are in a forest clearing. Paths lead east and south.",
            "cave": "You stand at the cave entrance. It is dim here; a lantern rests on the ground.",
            "tunnel": "A dark tunnel stretches north and south. It's hard to see without light.",
            "lake": "An underground lake glistens here. Something rusty lies near the water's edge.",
            "treasure": "A small chamber filled with chests and glittering hoards.",
        }

        # Items present at locations
        self.items_at: Dict[str, List[str]] = {
            "clearing": [],
            "cave": ["lantern"],
            "tunnel": [],
            "lake": ["rusty key"],
            "treasure": [],
        }

        self.current_location: str = "clearing"
        self.inventory: List[str] = []

        # Valid commands shown in help
        self.valid_commands = [
            "look",
            "go north",
            "go south",
            "go east",
            "go west",
            "take <item>",
            "inventory",
            "help",
            "quit",
        ]

        # Print title and initial description
        print("Lantern Cave")
        # On startup also show initial location description per contract
        print(self.descriptions[self.current_location])
        print(self.current_location)

    def parse_and_execute(self, command: str) -> bool:
        """Parse a single command string, execute it, print required lines.

        Returns True to continue the game loop, False to exit (quit or win).
        """
        if command is None:
            return True
        cmd = command.strip()
        if cmd == "":
            # Ignore empty commands but still show current location per rule? We'll treat as unknown.
            print("UNKNOWN COMMAND")
            print(self.current_location)
            return True

        lower = cmd.lower()

        # LOOK
        if lower == "look":
            print("LOOK")
            desc = self.descriptions.get(self.current_location, "You see nothing special.")
            print(desc)
            # Describe visible items
            items = self.items_at.get(self.current_location, [])
            if items:
                print("You see: " + ", ".join(items) + ".")
            print(self.current_location)
            return True

        # HELP
        if lower == "help":
            print("HELP")
            print("Available commands:")
            for c in self.valid_commands:
                print("  " + c)
            print(self.current_location)
            return True

        # INVENTORY
        if lower == "inventory":
            print("INVENTORY")
            if self.inventory:
                for it in self.inventory:
                    print(it)
            else:
                print("(empty)")
            print(self.current_location)
            return True

        # QUIT
        if lower == "quit":
            print("QUIT")
            # Print current location after command as required
            print(self.current_location)
            return False

        # TAKE <item>
        if lower.startswith("take "):
            item = cmd[5:].strip()
            # match item names case-insensitively
            items_here = self.items_at.get(self.current_location, [])
            match = None
            for it in items_here:
                if it.lower() == item.lower():
                    match = it
                    break
            if match:
                # Remove from location, add to inventory
                self.items_at[self.current_location].remove(match)
                self.inventory.append(match)
                print(f"TOOK {match}")
                print(f"You take the {match}.")
                print(self.current_location)
                return True
            else:
                # Cannot take what isn't here
                print("TOOK " + item)
                print(f"There is no {item} here.")
                print(self.current_location)
                return True

        # GO <direction>
        if lower.startswith("go "):
            dir_word = lower[3:].strip()
            if dir_word not in ("north", "south", "east", "west"):
                print("UNKNOWN COMMAND")
                print(self.current_location)
                return True

            # Check if an exit exists
            exits = self.map.get(self.current_location, {})
            dest = exits.get(dir_word)
            if not dest:
                print("BLOCKED")
                print("You can't go that way.")
                print(self.current_location)
                return True

            # Special rules: cannot enter tunnel without lantern
            if dest == "tunnel":
                if "lantern" not in (s.lower() for s in self.inventory):
                    print("BLOCKED")
                    print("It's too dark to enter the tunnel without a light.")
                    print(self.current_location)
                    return True

            # Special rule: treasure locked until rusty key
            if dest == "treasure":
                if "rusty key" not in (s.lower() for s in self.inventory):
                    print("BLOCKED")
                    print("The treasure room is locked. You need a key.")
                    print(self.current_location)
                    return True
                else:
                    # Move into treasure and win
                    # Update location then announce win
                    self.current_location = dest
                    dir_upper = dir_word.upper()
                    print(f"MOVED {dir_upper}")
                    print(self.descriptions[self.current_location])
                    print("WIN")
                    # As required, show current location after every command
                    print(self.current_location)
                    return False

            # Normal move allowed
            self.current_location = dest
            dir_upper = dir_word.upper()
            print(f"MOVED {dir_upper}")
            # Provide a short description of new location
            print(self.descriptions.get(self.current_location, "You arrive."))
            print(self.current_location)
            return True

        # Unknown command
        print("UNKNOWN COMMAND")
        print(self.current_location)
        return True

    def run(self) -> None:
        """Run the interactive loop until the game ends or EOF.

        Uses line-based input() so it works for redirected stdin as well as interactive play.
        """
        try:
            while True:
                # Prompt for input; print no extra prompt text to keep outputs predictable
                try:
                    line = input().rstrip("\n")
                except EOFError:
                    # Exit cleanly on EOF
                    return
                cont = self.parse_and_execute(line)
                if not cont:
                    return
        except KeyboardInterrupt:
            # Exit cleanly on Ctrl-C
            return


def main() -> None:
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
