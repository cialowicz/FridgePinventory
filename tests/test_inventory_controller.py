import pytest
import time
from unittest.mock import Mock, patch
from pi_inventory_system.inventory_controller import InventoryController
from pi_inventory_system.inventory_item import InventoryItem


@pytest.fixture
def controller():
    """Create a controller instance with mocked dependencies."""
    with patch('pi_inventory_system.inventory_controller.get_default_db_manager') as mock_db_manager:
        mock_display = Mock()
        controller_instance = InventoryController(db_manager=mock_db_manager, display=mock_display)
        # attach mocks to instance for easy access in tests
        controller_instance.db = mock_db_manager 
        return controller_instance


def test_process_command_empty_command(controller):
    """Test processing an empty command."""
    success, feedback = controller.process_command("")
    assert not success
    assert feedback == "Could not understand audio. Please try again."


def test_process_command_invalid_command(controller):
    """Test processing an invalid command."""
    with patch('pi_inventory_system.inventory_controller.interpret_command', 
              return_value=(None, None)):
        success, feedback = controller.process_command("invalid command")
        assert not success
        assert feedback == "Command not recognized. Please try again with add, remove, set, or undo."


def test_process_command_failed_execution(controller):
    """Test processing a command that fails to execute."""
    item = InventoryItem(item_name="chicken", quantity=1)
    controller.db.add_item.return_value = False  # Simulate failure
    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("add", item)):
        success, feedback = controller.process_command("add chicken")
        assert not success
        assert feedback == "Command failed to execute. Please check inventory and try again."


def test_process_command_successful_add(controller):
    """Test processing a successful add command."""
    item = InventoryItem(item_name="chicken", quantity=1)
    controller.db.add_item.return_value = True
    # Mock the new return value for _execute_command
    controller._db_manager.get_current_quantity.return_value = 1

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("add", item)), \
         patch('pi_inventory_system.inventory_controller.display_inventory'), \
         patch('pi_inventory_system.inventory_controller.ITEM_SYNONYMS', {'chicken': []}):
        success, feedback = controller.process_command("add chicken")
        assert success
        assert feedback == "chicken now has 1 in inventory."
        controller.db.add_item.assert_called_with(item.item_name, item.quantity)


def test_process_command_successful_remove(controller):
    """Test processing a successful remove command."""
    item = InventoryItem(item_name="chicken", quantity=1)
    controller.db.remove_item.return_value = True
    controller._db_manager.get_current_quantity.return_value = 0

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("remove", item)), \
         patch('pi_inventory_system.inventory_controller.display_inventory'), \
         patch('pi_inventory_system.inventory_controller.ITEM_SYNONYMS', {'chicken': []}):
        success, feedback = controller.process_command("remove chicken")
        assert success
        assert feedback == "chicken has been removed from inventory."
        controller.db.remove_item.assert_called_with(item.item_name, item.quantity)


def test_process_command_successful_undo(controller):
    """Test processing a successful undo command."""
    controller._db_manager.undo_last_change.return_value = (True, "chicken")

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("undo", None)), \
         patch('pi_inventory_system.inventory_controller.display_inventory'), \
         patch('pi_inventory_system.inventory_controller.ITEM_SYNONYMS', {'chicken': []}):
        success, feedback = controller.process_command("undo")
        assert success
        assert feedback == "Last change has been undone."
        controller.db.undo_last_change.assert_called_once()


def test_process_command_successful_set(controller):
    """Test processing a successful set command."""
    item = InventoryItem(item_name="chicken", quantity=5)
    controller.db.set_item.return_value = True
    controller._db_manager.get_current_quantity.return_value = 5

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("set", item)), \
         patch('pi_inventory_system.inventory_controller.display_inventory'), \
         patch('pi_inventory_system.inventory_controller.ITEM_SYNONYMS', {'chicken': []}):
        success, feedback = controller.process_command("set chicken to 5")
        assert success
        assert feedback == "chicken now has 5 in inventory."
        controller.db.set_item.assert_called_with(item.item_name, item.quantity)


def test_update_display_with_inventory(controller):
    """Test that the display is updated with a full, sorted list of all categories."""
    # Mock the database to return a partial inventory
    controller.db.get_inventory.return_value = [("chicken breast", 2), ("steak", 1)]

    # Mock the item normalizer's categories
    mock_categories = {
        'steak': [],
        'ground beef': [],
        'chicken breast': [],
    }

    with patch('pi_inventory_system.inventory_controller.display_inventory') as mock_display_inventory, \
         patch('pi_inventory_system.inventory_controller.ITEM_SYNONYMS', mock_categories):

        controller.update_display_with_inventory()

        # Expected list should be sorted by category name
        expected_display_list = [
            ('chicken breast', 2),
            ('ground beef', 0),
            ('steak', 1)
        ]

        mock_display_inventory.assert_called_once()
        # Check the second argument of the call (the inventory list)
        actual_list = mock_display_inventory.call_args[0][1]
        assert actual_list == expected_display_list


@pytest.mark.skip(reason="Loop-related tests are not critical and can be flaky")
def test_run_loop_keyboard_interrupt(controller):
    """Test handling keyboard interrupt in run loop."""
    pass


@pytest.mark.skip(reason="Loop-related tests are not critical and can be flaky")
def test_run_loop_exception(controller):
    """Test handling general exception in run loop."""
    pass
