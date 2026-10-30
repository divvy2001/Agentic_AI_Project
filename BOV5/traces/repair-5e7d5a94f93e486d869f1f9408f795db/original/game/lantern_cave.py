import os
import sys
import pygame

# Ensure module runs as script or module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
FPS = 30
TITLE = "Lantern Cave"

# Game state and data owned by this module
class LanternCaveGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.big_font = pygame.font.Font(None, 32)

        # World state
        # location keys: 'forest', 'cave', 'dark_tunnel', 'lake', 'treasure'
        self.locations = {
            'forest': {
                'name': 'Forest Clearing',
                'description': 'You are in a quiet forest clearing. Paths lead east and south.',
                'items': [],
                'exits': {'east': 'cave', 'south': 'lake'}
            },
            'cave': {
                'name': 'Cave Entrance',
                'description': 'You stand at the cave entrance. It is dim. Paths lead west and east.',
                'items': ['lantern'],
                'exits': {'west': 'forest', 'east': 'dark_tunnel'}
            },
            'dark_tunnel': {
                'name': 'Dark Tunnel',
                'description': 'A pitch-black tunnel stretches ahead. You cannot see without light. Paths lead west and east.',
                'items': [],
                'exits': {'west': 'cave', 'east': 'treasure'}
            },
            'lake': {
                'name': 'Underground Lake',
                'description': 'A cold underground lake glistens. Paths lead north.',
                'items': ['rusty key'],
                'exits': {'north': 'forest'}
            },
            'treasure': {
                'name': 'Treasure Room',
                'description': 'A small chamber filled with chests and glittering things.',
                'items': [],
                'exits': {}
            }
        }

        self.current_location = 'forest'
        self.inventory = []  # list of item names

        # Input state
        self.input_text = ''
        self.output_lines = []  # lines to display beneath the location

        # Draw initial description
        self.append_location_description()

    def append_output(self, line: str):
        # Keep last ~10 lines
        self.output_lines.append(line)
        if len(self.output_lines) > 10:
            self.output_lines.pop(0)

    def append_location_description(self):
        loc = self.locations[self.current_location]
        # Always show location name and description after commands
        self.append_output(f"Location: {loc['name']}")
        self.append_output(loc['description'])
        if loc['items']:
            items_str = ', '.join(loc['items'])
            self.append_output(f"You see here: {items_str}")

    def process_command(self, raw: str):
        cmd = raw.strip()
        if not cmd:
            return
        cmd_l = cmd.lower()

        # Commands: look, go north/south/east/west, take <item>, inventory, help, quit
        if cmd_l == 'look':
            print('LOOK', flush=True)
            # After confirmation, show location description
            self.append_output('LOOK')
            self.append_location_description()
            return

        if cmd_l.startswith('go '):
            parts = cmd_l.split()
            if len(parts) >= 2:
                direction = parts[1]
                if direction in ('north', 'south', 'east', 'west'):
                    # Attempt to move
                    target = self.locations[self.current_location]['exits'].get(direction)
                    if not target:
                        print('BLOCKED', flush=True)
                        self.append_output('BLOCKED')
                        # still show current location
                        self.append_location_description()
                        return
                    # Movement special checks
                    if target == 'dark_tunnel' and 'lantern' not in self.inventory:
                        print('BLOCKED', flush=True)
                        self.append_output('BLOCKED')
                        self.append_location_description()
                        return
                    if target == 'treasure' and 'rusty key' not in self.inventory:
                        print('BLOCKED', flush=True)
                        self.append_output('BLOCKED')
                        self.append_location_description()
                        return
                    # Successful move
                    dir_up = direction.upper()
                    print(f'MOVED {dir_up}', flush=True)
                    self.append_output(f'MOVED {dir_up}')
                    # change location
                    self.current_location = target
                    # Show new location
                    self.append_location_description()
                    # Check win condition: entering treasure while having rusty key
                    if self.current_location == 'treasure' and 'rusty key' in self.inventory:
                        print('WIN', flush=True)
                        # Also show WIN in output and then exit cleanly
                        self.append_output('WIN')
                        self.draw()  # draw one final frame so user can see
                        pygame.time.delay(500)
                        pygame.quit()
                        sys.exit(0)
                    return
            # If parsing failed
            print('UNKNOWN COMMAND', flush=True)
            self.append_output('UNKNOWN COMMAND')
            self.append_location_description()
            return

        if cmd_l.startswith('take '):
            item = cmd[5:].strip()  # preserve case of item as typed? Use lower-case matching
            item_l = item.lower()
            # Find item in current location by lower-case match
            loc_items = self.locations[self.current_location]['items']
            found = None
            for it in loc_items:
                if it.lower() == item_l:
                    found = it
                    break
            if found:
                # Take it
                loc_items.remove(found)
                self.inventory.append(found)
                print(f'TOOK {found}', flush=True)
                self.append_output(f'TOOK {found}')
                self.append_location_description()
                return
            else:
                # Not present
                print('BLOCKED', flush=True)
                self.append_output('BLOCKED')
                self.append_location_description()
                return

        if cmd_l == 'inventory':
            print('INVENTORY', flush=True)
            self.append_output('INVENTORY')
            if self.inventory:
                for it in self.inventory:
                    self.append_output(f'- {it}')
            else:
                self.append_output(' (empty)')
            # also show current location
            self.append_location_description()
            return

        if cmd_l == 'help':
            print('HELP', flush=True)
            self.append_output('HELP')
            self.append_output('Commands: look, go north/south/east/west, take <item>, inventory, help, quit')
            self.append_location_description()
            return

        if cmd_l == 'quit':
            print('QUIT', flush=True)
            self.append_output('QUIT')
            self.draw()
            pygame.time.delay(200)
            pygame.quit()
            sys.exit(0)

        # Unknown command
        print('UNKNOWN COMMAND', flush=True)
        self.append_output('UNKNOWN COMMAND')
        self.append_location_description()

    def draw(self):
        self.screen.fill((0, 0, 0))

        # Title
        title_surf = self.big_font.render(TITLE, True, (255, 255, 0))
        self.screen.blit(title_surf, (20, 10))

        # Draw output lines
        start_y = 60
        y = start_y
        for line in self.output_lines:
            surf = self.font.render(line, True, (255, 255, 255))
            self.screen.blit(surf, (20, y))
            y += 24

        # Draw input prompt
        prompt = '> ' + self.input_text
        prompt_surf = self.font.render(prompt, True, (180, 180, 180))
        self.screen.blit(prompt_surf, (20, WINDOW_HEIGHT - 40))

        pygame.display.flip()

    def run(self):
        running = True
        # Enable text input events (useful in some SDL backends)
        try:
            pygame.key.start_text_input()
        except Exception:
            # not all pygame builds expose start_text_input
            pass

        while running:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    # Follow Pygame playbook: quit on window close
                    pygame.quit()
                    sys.exit(0)
                # Some test harnesses send TEXTINPUT events rather than KEYDOWN with unicode
                elif event.type == pygame.TEXTINPUT:
                    # event.text contains the input characters
                    self.input_text += event.text
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                    elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                        # Process the current input as a command
                        cmd = self.input_text
                        self.input_text = ''
                        self.process_command(cmd)
                    elif event.key == pygame.K_ESCAPE:
                        # Quit on ESC (not required by plan but allowed)
                        print('QUIT', flush=True)
                        self.append_output('QUIT')
                        self.draw()
                        pygame.time.delay(100)
                        pygame.quit()
                        sys.exit(0)
                    else:
                        # Add character to input (ignore modifiers)
                        # KEYDOWN may provide event.unicode on some platforms
                        char = getattr(event, 'unicode', '')
                        if char:
                            self.input_text += char
            self.draw()


if __name__ == '__main__':
    game = LanternCaveGame()
    game.run()
