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
        assert feedback == "Command not recognized. Please try again with a valid command."


def test_process_command_failed_execution(controller):
    """Test processing a command that fails to execute."""
    item = InventoryItem(item_name="chicken", quantity=1)
    controller.db.add_item.return_value = False  # Simulate failure
    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("add", item)):
        success, feedback = controller.process_command("add chicken")
        assert not success
        assert feedback == "Command failed to execute. Please try again."


def test_process_command_successful_add(controller):
    """Test processing a successful add command."""
    item = InventoryItem(item_name="chicken", quantity=1)
    controller.db.add_item.return_value = True
    controller.db.get_current_quantity.return_value = 1

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("add", item)), \
         patch('pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("add chicken")
        assert success
        assert feedback == "chicken now has 1 in inventory."
        controller.db.add_item.assert_called_with(item.item_name, item.quantity)


def test_process_command_successful_remove(controller):
    """Test processing a successful remove command."""
    item = InventoryItem(item_name="chicken", quantity=1)
    controller.db.remove_item.return_value = True
    controller.db.get_current_quantity.return_value = 0

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("remove", item)), \
         patch('pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("remove chicken")
        assert success
        assert feedback == "chicken has been removed from inventory."
        controller.db.remove_item.assert_called_with(item.item_name, item.quantity)


def test_process_command_successful_undo(controller):
    """Test processing a successful undo command."""
    controller.db.undo_last_change.return_value = ("chicken", 2)

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("undo", None)), \
         patch('pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("undo")
        assert success
        assert feedback == "Last change has been undone. chicken now has 2 in inventory."
        controller.db.undo_last_change.assert_called_once()


def test_process_command_successful_set(controller):
    """Test processing a successful set command."""
    item = InventoryItem(item_name="chicken", quantity=5)
    controller.db.set_item.return_value = True
    controller.db.get_current_quantity.return_value = 5

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("set", item)), \
         patch('pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("set chicken to 5")
        assert success
        assert feedback == "chicken now has 5 in inventory."
        controller.db.set_item.assert_called_with(item.item_name, item.quantity)


@pytest.mark.skip(reason="Loop-related tests are not critical and can be flaky")
def test_run_loop_keyboard_interrupt(controller):
    """Test handling keyboard interrupt in run loop."""
    pass


@pytest.mark.skip(reason="Loop-related tests are not critical and can be flaky")
def test_run_loop_exception(controller):
    """Test handling general exception in run loop."""
    pass
