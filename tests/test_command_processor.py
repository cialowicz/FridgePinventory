# Tests for command processor

import pytest
from unittest.mock import MagicMock
from pi_inventory_system.command_processor import interpret_command
from pi_inventory_system.inventory_item import InventoryItem

@pytest.fixture
def mock_config_manager():
    """Mock the config manager."""
    config_manager = MagicMock()
    config_manager.get_command_config.return_value = {}
    config_manager.get_nlp_config.return_value = {'enable_spacy': False}
    return config_manager

def test_add_command(mock_config_manager):
    command_type, item = interpret_command("Add 3 chicken tenders", mock_config_manager)
    assert command_type == "add"
    assert item == InventoryItem(item_name="chicken tenders", quantity=3)

def test_remove_command(mock_config_manager):
    command_type, item = interpret_command("Remove 2 salmon", mock_config_manager)
    assert command_type == "remove"
    assert item == InventoryItem(item_name="salmon", quantity=2)

def test_set_command(mock_config_manager):
    command_type, item = interpret_command("Set ice cream to 5", mock_config_manager)
    assert command_type == "set"
    assert item == InventoryItem(item_name="ice cream", quantity=5)

def test_undo_command(mock_config_manager):
    command_type, item = interpret_command("Undo", mock_config_manager)
    assert command_type == "undo"
    assert item is None

def test_unrecognized_command(mock_config_manager):
    command_type, item = interpret_command("Fly to the moon", mock_config_manager)
    assert command_type is None
    assert item is None

def test_tilapia_normalization(mock_config_manager):
    """Test that tilapia is correctly normalized to white fish."""
    command_type, item = interpret_command("Set tilapia to 3", mock_config_manager)
    assert command_type == "set"
    assert item == InventoryItem(item_name="white fish", quantity=3)

def test_to_vs_two_disambiguation(mock_config_manager):
    """Test that 'to' is not interpreted as 'two' in set commands."""
    # Test with "to"
    command_type, item = interpret_command("Set salmon to 3", mock_config_manager)
    assert command_type == "set"
    assert item == InventoryItem(item_name="salmon", quantity=3)

    # Test with "two"
    command_type, item = interpret_command("Add two salmon", mock_config_manager)
    assert command_type == "add"
    assert item == InventoryItem(item_name="salmon", quantity=2)

@pytest.mark.parametrize("command,expected_type", [
    ("Set tilapia to 3", "set"),
    ("Set tilapia fillet to 3", "set"),
    ("Set tilapia fillets to 3", "set"),
    ("Add 3 tilapia", "add"),
    ("Remove 2 tilapia fillet", "remove")
])
def test_various_tilapia_forms(command, expected_type, mock_config_manager):
    """Test different forms of tilapia are correctly normalized."""
    command_type, item = interpret_command(command, mock_config_manager)
    assert command_type == expected_type
    assert item.item_name == "white fish"
