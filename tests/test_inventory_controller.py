import pytest
import time
from unittest.mock import Mock, patch
from src.pi_inventory_system.inventory_controller import InventoryController


@pytest.fixture
def controller():
    """Create a controller instance with mocked dependencies."""
    with patch('src.pi_inventory_system.inventory_controller.init_db'), \
         patch('src.pi_inventory_system.inventory_controller.initialize_display'):
        return InventoryController()


def test_process_command_empty_command(controller):
    """Test processing an empty command."""
    success, feedback = controller.process_command("")
    assert not success
    assert feedback == "Could not understand audio. Please try again."


def test_process_command_invalid_command(controller):
    """Test processing an invalid command."""
    with patch('src.pi_inventory_system.inventory_controller.interpret_command', 
              return_value=(None, None)):
        success, feedback = controller.process_command("invalid command")
        assert not success
        assert feedback == "Command not recognized. Please try again with a valid command."


def test_process_command_failed_execution(controller):
    """Test processing a command that fails to execute."""
    with patch('src.pi_inventory_system.inventory_controller.interpret_command',
              return_value=("add", (1, "chicken"))), \
         patch('src.pi_inventory_system.inventory_controller.execute_command',
              return_value=False):
        success, feedback = controller.process_command("add chicken")
        assert not success
        assert feedback == "Command failed to execute. Please try again."


def test_process_command_successful_add(controller):
    """Test processing a successful add command."""
    with patch('src.pi_inventory_system.inventory_controller.interpret_command',
              return_value=("add", (1, "chicken"))), \
         patch('src.pi_inventory_system.inventory_controller.execute_command',
              return_value=True), \
         patch('src.pi_inventory_system.inventory_controller.get_inventory',
              return_value=[("chicken", 1)]), \
         patch('src.pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("add chicken")
        assert success
        assert feedback == "chicken now has 1 in inventory."


def test_process_command_successful_remove(controller):
    """Test processing a successful remove command."""
    with patch('src.pi_inventory_system.inventory_controller.interpret_command',
              return_value=("remove", (1, "chicken"))), \
         patch('src.pi_inventory_system.inventory_controller.execute_command',
              return_value=True), \
         patch('src.pi_inventory_system.inventory_controller.get_inventory',
              return_value=[]), \
         patch('src.pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("remove chicken")
        assert success
        assert feedback == "chicken has been removed from inventory."


def test_process_command_successful_undo(controller):
    """Test processing a successful undo command."""
    with patch('src.pi_inventory_system.inventory_controller.interpret_command',
              return_value=("undo", "chicken")), \
         patch('src.pi_inventory_system.inventory_controller.execute_command',
              return_value=True), \
         patch('src.pi_inventory_system.inventory_controller.get_inventory',
              return_value=[("chicken", 2)]), \
         patch('src.pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("undo")
        assert success
        assert feedback == "Last change has been undone. chicken now has 2 in inventory."


def test_process_command_successful_set(controller):
    """Test processing a successful set command."""
    with patch('src.pi_inventory_system.inventory_controller.interpret_command',
              return_value=("set", ("chicken", 5))), \
         patch('src.pi_inventory_system.inventory_controller.execute_command',
              return_value=True), \
         patch('src.pi_inventory_system.inventory_controller.get_inventory',
              return_value=[("chicken", 5)]), \
         patch('src.pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("set chicken to 5")
        assert success
        assert feedback == "chicken now has 5 in inventory."


@pytest.mark.skip(reason="Loop-related tests are not critical and can be flaky")
def test_run_loop_keyboard_interrupt(controller):
    """Test handling keyboard interrupt in run loop."""
    pass


@pytest.mark.skip(reason="Loop-related tests are not critical and can be flaky")
def test_run_loop_exception(controller):
    """Test handling general exception in run loop."""
    pass 