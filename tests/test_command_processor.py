# Tests for command processor module

import pytest
from unittest.mock import patch, MagicMock
from pi_inventory_system.command_processor import interpret_command
from pi_inventory_system.inventory_item import InventoryItem

def test_add_command():
    command_type, item = interpret_command("Add 3 chicken tenders")
    assert command_type == "add"
    assert item == InventoryItem(item_name="chicken tenders", quantity=3)

def test_remove_command():
    command_type, item = interpret_command("Remove 2 salmon")
    assert command_type == "remove"
    assert item == InventoryItem(item_name="salmon", quantity=2)

def test_set_command():
    command_type, item = interpret_command("Set ice cream to 5")
    assert command_type == "set"
    assert item == InventoryItem(item_name="ice cream", quantity=5)

def test_undo_command():
    command_type, item = interpret_command("Undo")
    assert command_type == "undo"
    assert item is None

def test_unrecognized_command():
    command_type, item = interpret_command("Fly to the moon")
    assert command_type is None
    assert item is None

def test_tilapia_normalization():
    """Test that tilapia is correctly normalized to white fish."""
    command_type, item = interpret_command("Set tilapia to 3")
    assert command_type == "set"
    assert item == InventoryItem(item_name="white fish", quantity=3)

def test_to_vs_two_disambiguation():
    """Test that 'to' is not interpreted as 'two' in set commands."""
    # Test with "to"
    command_type, item = interpret_command("Set salmon to 3")
    assert command_type == "set"
    assert item == InventoryItem(item_name="salmon", quantity=3)

    # Test with "two" to ensure it's not interpreted as a set command
    command_type, item = interpret_command("Add two salmon")
    assert command_type == "add"
    assert item == InventoryItem(item_name="salmon", quantity=2)

@pytest.mark.parametrize("command,expected_type", [
    ("Set tilapia to 3", "set"),
    ("Set tilapia fillet to 3", "set"),
    ("Set tilapia fillets to 3", "set"),
    ("Add 3 tilapia", "add"),
    ("Remove 2 tilapia fillet", "remove")
])
def test_various_tilapia_forms(command, expected_type):
    """Test different forms of tilapia are correctly normalized."""
    command_type, item = interpret_command(command)
    assert command_type == expected_type
    assert item.item_name == "white fish"
