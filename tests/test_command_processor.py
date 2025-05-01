# Tests for command processor module

import unittest
from unittest.mock import patch, MagicMock
from src.pi_inventory_system.command_processor import (
    interpret_command,
    add_item,
    remove_item,
    set_item,
    get_inventory
)
from src.pi_inventory_system.inventory_item import InventoryItem


class TestCommandProcessor(unittest.TestCase):

    def test_add_command(self):
        command_type, item = interpret_command("Add 3 chicken tenders")
        self.assertEqual(command_type, "add")
        self.assertEqual(item, InventoryItem(item_name="chicken tenders", quantity=3))

    def test_remove_command(self):
        command_type, item = interpret_command("Remove 2 salmon")
        self.assertEqual(command_type, "remove")
        self.assertEqual(item, InventoryItem(item_name="salmon", quantity=2))

    def test_set_command(self):
        command_type, item = interpret_command("Set ice cream to 5")
        self.assertEqual(command_type, "set")
        self.assertEqual(item, InventoryItem(item_name="ice cream", quantity=5))

    def test_undo_command(self):
        command_type, item = interpret_command("Undo")
        self.assertEqual(command_type, "undo")
        self.assertIsNone(item)

    def test_unrecognized_command(self):
        command_type, item = interpret_command("Fly to the moon")
        self.assertIsNone(command_type)
        self.assertIsNone(item)

    def test_tilapia_normalization(self):
        """Test that tilapia is correctly normalized to white fish."""
        command_type, item = interpret_command("Set tilapia to 3")
        self.assertEqual(command_type, "set")
        self.assertEqual(item, InventoryItem(item_name="white fish", quantity=3))

    def test_to_vs_two_disambiguation(self):
        """Test that 'to' is not interpreted as 'two' in set commands."""
        # Test with "to"
        command_type, item = interpret_command("Set salmon to 3")
        self.assertEqual(command_type, "set")
        self.assertEqual(item, InventoryItem(item_name="salmon", quantity=3))

        # Test with "two" to ensure it's not interpreted as a set command
        command_type, item = interpret_command("Add two salmon")
        self.assertEqual(command_type, "add")
        self.assertEqual(item, InventoryItem(item_name="salmon", quantity=2))

    def test_various_tilapia_forms(self):
        """Test different forms of tilapia are correctly normalized."""
        test_cases = [
            ("Set tilapia to 3", "set"),
            ("Set tilapia fillet to 3", "set"),
            ("Set tilapia fillets to 3", "set"),
            ("Add 3 tilapia", "add"),
            ("Remove 2 tilapia fillet", "remove")
        ]
        
        for command, expected_type in test_cases:
            command_type, item = interpret_command(command)
            self.assertEqual(command_type, expected_type)
            self.assertEqual(item.item_name, "white fish")


if __name__ == '__main__':
    unittest.main()
