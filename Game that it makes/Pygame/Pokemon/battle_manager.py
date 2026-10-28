import random
from typing import List, Dict, Optional
from .creature import Creature


class BattleManager:
    """Manages turn-based battle logic between player and enemy.

    Attributes:
        player (Creature)
        enemy (Creature)
        state (str): 'player', 'message', 'win', 'lose'
        messages (List[str])
        message_index (int)
        message_timer (float)
        pending_state (Optional[str])
    """

    MESSAGE_DURATION = 1.4

    def __init__(self, player: Creature, enemy: Creature):
        self.player = player
        self.enemy = enemy
        self.state = 'player'
        self.messages: List[str] = []
        self.message_index = 0
        self.message_timer = 0.0
        self.pending_state: Optional[str] = None

    def reset(self) -> None:
        self.player.reset()
        self.enemy.reset()
        self.state = 'player'
        self.messages = []
        self.message_index = 0
        self.message_timer = 0.0
        self.pending_state = None

    def is_input_allowed(self) -> bool:
        return self.state == 'player'

    def player_use_move(self, move_index: int) -> None:
        if not self.is_input_allowed():
            return
        # guard index
        if move_index < 0 or move_index >= len(self.player.moves):
            return
        self.messages = []
        self.message_index = 0
        self.message_timer = self.MESSAGE_DURATION
        self.pending_state = None

        move = self.player.moves[move_index]
        # Player move message
        self.messages.append(f"{self.player.name} used {move['name']}!")

        if move.get('category', 'damage') == 'heal':
            amount = move.get('power', 0)
            healed = self.player.heal(amount)
            self.messages.append(f"{self.player.name} healed for {healed} HP!")
            if healed > 0:
                print(f"[EVENT] HEAL:{healed}")
        else:
            damage = self.calculate_damage(move, self.player, self.enemy)
            actual = self.enemy.take_damage(damage)
            self.messages.append(f"It dealt {actual} damage!")
            if actual > 0:
                print(f"[EVENT] DAMAGE:{actual}")
            if not self.enemy.is_alive():
                self.messages.append(f"{self.enemy.name} fainted!")
                self.pending_state = 'win'

        # If enemy still alive, enemy takes a turn
        if self.enemy.is_alive():
            enemy_move = random.choice(self.enemy.moves)
            self.messages.append(f"{self.enemy.name} used {enemy_move['name']}!")
            if enemy_move.get('category', 'damage') == 'heal':
                amt = enemy_move.get('power', 0)
                healed = self.enemy.heal(amt)
                self.messages.append(f"{self.enemy.name} healed for {healed} HP!")
                if healed > 0:
                    print(f"[EVENT] ENEMY_HEAL:{healed}")
            else:
                dmg = self.calculate_damage(enemy_move, self.enemy, self.player)
                actual2 = self.player.take_damage(dmg)
                self.messages.append(f"It dealt {actual2} damage!")
                if actual2 > 0:
                    print(f"[EVENT] DAMAGE_TO_PLAYER:{actual2}")
                if not self.player.is_alive():
                    self.messages.append(f"{self.player.name} fainted!")
                    # If player fainted, pending state is lose, even if enemy later dies (unlikely)
                    self.pending_state = 'lose'

        # Start message display
        self.state = 'message'
        self.message_index = 0
        self.message_timer = self.MESSAGE_DURATION

    def calculate_damage(self, move: Dict, attacker: Creature, defender: Creature) -> int:
        # Base damage is move power
        base = move.get('power', 0)
        # Apply type effectiveness: water does double to fire
        mtype = move.get('type', 'neutral')
        multiplier = 1.0
        if mtype == 'water' and defender.type == 'fire':
            multiplier = 2.0
        # Simple defense calculation included in Creature.take_damage
        raw = int(base * multiplier)
        return raw

    def update(self, dt: float) -> None:
        if self.state != 'message':
            return
        self.message_timer -= dt
        if self.message_timer > 0:
            return
        # advance to next message
        self.message_index += 1
        if self.message_index >= len(self.messages):
            # messages finished
            if self.pending_state == 'win':
                self.state = 'win'
                print("[EVENT] WIN")
            elif self.pending_state == 'lose':
                self.state = 'lose'
                print("[EVENT] LOSE")
            else:
                self.state = 'player'
            # clear messages after showing final message for a short time
            self.messages = []
            self.message_index = 0
            self.message_timer = 0.0
            self.pending_state = None
        else:
            # reset timer for next message
            self.message_timer = self.MESSAGE_DURATION

    def get_current_message(self) -> Optional[str]:
        if self.state != 'message':
            return None
        if 0 <= self.message_index < len(self.messages):
            return self.messages[self.message_index]
        return None
