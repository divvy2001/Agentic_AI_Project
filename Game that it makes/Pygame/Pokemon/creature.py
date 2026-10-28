from typing import List, Dict

class Creature:
    """Represents a battling creature.

    Attributes:
        name (str)
        type (str): elemental type, e.g. 'fire' or 'water' or 'neutral'
        max_hp (int)
        hp (int)
        defense (int)
        base_defense (int)
        moves (List[Dict]): each move is a dict with keys: name,type,power,category
    """

    def __init__(self, name: str, ctype: str, max_hp: int, defense: int, moves: List[Dict]):
        self.name = name
        self.type = ctype
        self.max_hp = max_hp
        self.hp = max_hp
        self.defense = defense
        self.base_defense = defense
        self.moves = moves

    def take_damage(self, amount: int) -> int:
        """Apply damage after defense and reduce hp. Returns actual HP lost."""
        # Simple damage formula: subtract defense from amount
        actual = max(0, amount - self.defense)
        # Ensure at least 1 damage if amount>0
        if amount > 0 and actual == 0:
            actual = 1
        self.hp = max(0, self.hp - actual)
        return actual

    def heal(self, amount: int) -> int:
        prev = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - prev

    def reset(self) -> None:
        self.hp = self.max_hp
        self.defense = self.base_defense

    def is_alive(self) -> bool:
        return self.hp > 0

    def __repr__(self) -> str:
        return f"Creature({self.name}, hp={self.hp}/{self.max_hp}, def={self.defense})"
