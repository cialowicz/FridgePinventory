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


@pytest.mark.parametrize("command", [
    "set salmon to many",
    "set salmon to",
    "set to 3",
])
def test_set_command_requires_explicit_quantity(command, mock_config_manager):
    command_type, item = interpret_command(command, mock_config_manager)
    assert command_type == "set"
    assert item is None

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


@pytest.mark.parametrize("command,expected_type,expected_item,expected_qty", [
    ("Add 3 of chicken tenders", "add", "chicken tenders", 3),
    ("Remove 2 of salmon", "remove", "salmon", 2),
    ("Stock 2 salmon", "add", "salmon", 2),
    ("Bought 2 salmon", "add", "salmon", 2),
    ("Add a dozen salmon", "add", "salmon", 12),
    ("Change salmon to 3", "set", "salmon", 3),
])
def test_documented_and_synonym_forms(
    command,
    expected_type,
    expected_item,
    expected_qty,
    mock_config_manager,
):
    command_type, item = interpret_command(command, mock_config_manager)
    assert command_type == expected_type
    assert item == InventoryItem(item_name=expected_item, quantity=expected_qty)

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


def test_empty_string_returns_none(mock_config_manager):
    assert interpret_command("", mock_config_manager) == (None, None)


def test_oversized_command_rejected(mock_config_manager):
    assert interpret_command("a" * 600, mock_config_manager) == (None, None)


def test_non_string_input_returns_none(mock_config_manager):
    assert interpret_command(None, mock_config_manager) == (None, None)


def test_default_quantity_is_one(mock_config_manager):
    """Add commands with no number-word default to 1."""
    command_type, item = interpret_command("add salmon", mock_config_manager)
    assert command_type == "add"
    assert item.quantity == 1


@pytest.mark.parametrize("command", [
    "add 10001 salmon",
    "add -1 salmon",
    "remove 10001 salmon",
])
def test_invalid_leading_quantities_do_not_become_item_names(command, mock_config_manager):
    command_type, item = interpret_command(command, mock_config_manager)
    assert command_type in {"add", "remove"}
    assert item is None


def test_remove_all_maps_to_clamping_remove(mock_config_manager):
    command_type, item = interpret_command("remove all salmon", mock_config_manager)
    assert command_type == "remove"
    assert item == InventoryItem(item_name="salmon", quantity=10000)


@pytest.mark.parametrize("command,expected_type", [
    ("add chicken stock", "add"),
    ("remove chicken stock", "remove"),
])
def test_command_words_can_be_part_of_item_names(command, expected_type, mock_config_manager):
    command_type, item = interpret_command(command, mock_config_manager)

    assert command_type == expected_type
    assert item == InventoryItem(item_name="chicken stock", quantity=1)


@pytest.mark.parametrize("command,expected_type,expected_item", [
    ("please add salmon", "add", "salmon"),
    ("i bought salmon", "add", "salmon"),
])
def test_non_leading_command_verbs_preserve_item_phrase(
    command,
    expected_type,
    expected_item,
    mock_config_manager,
):
    command_type, item = interpret_command(command, mock_config_manager)

    assert command_type == expected_type
    assert item == InventoryItem(item_name=expected_item, quantity=1)


def test_have_no_longer_classified_as_set(mock_config_manager):
    """Questions like 'do you have salmon' should not register as set."""
    command_type, _ = interpret_command("do you have salmon", mock_config_manager)
    assert command_type is None


@pytest.mark.parametrize("command,expected_type", [
    # Words *containing* an undo keyword must not classify as undo.
    ("add 2 cancelled-order steaks", "add"),
    ("remove 1 reversed jacket", "remove"),
    # Real undo phrasings still classify as undo.
    ("cancel that", "undo"),
    ("take back the last one", "undo"),
    ("revert", "undo"),
])
def test_undo_words_match_on_word_boundaries(command, expected_type, mock_config_manager):
    command_type, _ = interpret_command(command, mock_config_manager)
    assert command_type == expected_type
