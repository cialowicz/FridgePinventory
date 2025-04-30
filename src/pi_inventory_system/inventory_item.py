# Module for inventory item representation

from dataclasses import dataclass
from typing import Optional

@dataclass
class InventoryItem:
    """Class representing an inventory item with its quantity."""
    item_name: str
    quantity: int

    def __post_init__(self):
        """Validate the item after initialization."""
        if not isinstance(self.item_name, str):
            raise ValueError("item_name must be a string")
        if not isinstance(self.quantity, int):
            raise ValueError("quantity must be an integer")
        if self.quantity < 0:
            raise ValueError("quantity cannot be negative")

    @classmethod
    def from_tuple(cls, item_tuple: tuple) -> 'InventoryItem':
        """Create an InventoryItem from a tuple of (item_name, quantity)."""
        if len(item_tuple) != 2:
            raise ValueError("Tuple must have exactly 2 elements")
        return cls(str(item_tuple[0]), int(item_tuple[1]))

    def to_tuple(self) -> tuple[str, int]:
        """Convert the item to a tuple of (item_name, quantity)."""
        return (self.item_name, self.quantity) 