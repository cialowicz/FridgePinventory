# Tests for command processor module

import unittest
from unittest.mock import patch, MagicMock
from pi_inventory_system.command_processor import (
    interpret_command,
    add_item,
    remove_item,
    set_item,
    get_inventory
)


class TestCommandProcessor(unittest.TestCase):

    def test_add_command(self):
        command_type, details = interpret_command("Add 3 chicken tenders")
        self.assertEqual(command_type, "add")
        self.assertEqual(details, (3, "chicken tenders"))

    def test_remove_command(self):
        command_type, details = interpret_command("Remove 2 salmon")
        self.assertEqual(command_type, "remove")
        self.assertEqual(details, (2, "salmon"))

    def test_set_command(self):
        command_type, details = interpret_command("Set ice cream to 5")
        self.assertEqual(command_type, "set")
        self.assertEqual(details, ("ice cream", 5))

    def test_undo_command(self):
        command_type, details = interpret_command("Undo")
        self.assertEqual(command_type, "undo")
        self.assertIsNone(details)

    def test_unrecognized_command(self):
        command_type, details = interpret_command("Fly to the moon")
        self.assertIsNone(command_type)
        self.assertIsNone(details)

    def test_tilapia_normalization(self):
        """Test that tilapia is correctly normalized to white fish."""
        command_type, details = interpret_command("Set tilapia to 3")
        self.assertEqual(command_type, "set")
        self.assertEqual(details, ("white fish", 3))

    def test_to_vs_two_disambiguation(self):
        """Test that 'to' is not interpreted as 'two' in set commands."""
        # Test with "to"
        command_type, details = interpret_command("Set salmon to 3")
        self.assertEqual(command_type, "set")
        self.assertEqual(details, ("salmon", 3))

        # Test with "two" to ensure it's not interpreted as a set command
        command_type, details = interpret_command("Add two salmon")
        self.assertEqual(command_type, "add")
        self.assertEqual(details, (2, "salmon"))

    def test_various_tilapia_forms(self):
        """Test different forms of tilapia are correctly normalized."""
        test_cases = [
            "Set tilapia to 3",
            "Set tilapia fillet to 3",
            "Set tilapia fillets to 3",
            "Add 3 tilapia",
            "Remove 2 tilapia fillet"
        ]
        
        for command in test_cases:
            command_type, details = interpret_command(command)
            if command_type == "set":
                self.assertEqual(details[0], "white fish")
            else:
                self.assertEqual(details[1], "white fish")


if __name__ == '__main__':
    unittest.main()
