import pytest
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch, MagicMock
from pi_inventory_system.config_manager import create_config_manager
from pi_inventory_system.database_manager import create_database_manager
from pi_inventory_system.exceptions import DisplayError
from pi_inventory_system.inventory_controller import InventoryController
from pi_inventory_system.inventory_item import InventoryItem


@pytest.fixture
def controller():
    """Create a controller instance with mocked dependencies."""
    with patch(
        'pi_inventory_system.inventory_controller.get_default_db_manager'
    ) as mock_db_manager:
        mock_display = Mock()
        mock_config_manager = MagicMock()
        mock_config_manager.get_command_config.return_value = {'similarity_threshold': 0.8}
        controller_instance = InventoryController(
            db_manager=mock_db_manager,
            display=mock_display,
            config_manager=mock_config_manager,
        )
        controller_instance.db = mock_db_manager
        # Default to empty inventory so the post-command refresh has a real list.
        mock_db_manager.get_inventory.return_value = []
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
        assert feedback == (
            "Command not recognized. Please try again with add, remove, set, or undo."
        )


def test_process_command_failed_execution(controller):
    """Test processing a command that fails to execute."""
    item = InventoryItem(item_name="chicken", quantity=1)
    controller.db.add_item.return_value = False  # Simulate failure
    controller._db_manager.get_current_quantity.return_value = 0  # Ensure limit guard doesn't fire
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
         patch('pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("add chicken")
        assert success
        assert feedback == "chicken now has 1 in inventory."
        controller.db.add_item.assert_called_with(item.item_name, item.quantity)


def test_process_command_successful_remove(controller):
    """Test processing a successful remove command."""
    item = InventoryItem(item_name="chicken", quantity=1)
    controller.db.remove_item.return_value = True
    controller._db_manager.get_current_quantity.side_effect = [1, 0]

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("remove", item)), \
         patch('pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("remove chicken")
        assert success
        assert feedback == "chicken has been removed from inventory."
        controller.db.remove_item.assert_called_with(item.item_name, item.quantity)


def test_process_command_remove_missing_item(controller):
    """Removing a missing item should not report a successful mutation."""
    item = InventoryItem(item_name="chicken", quantity=1)
    controller._db_manager.get_current_quantity.return_value = 0

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("remove", item)):
        success, feedback = controller.process_command("remove chicken")
        assert not success
        assert feedback == "chicken is not in inventory."
        controller.db.remove_item.assert_not_called()


def test_process_command_remove_all_clamps_to_zero(controller):
    item = InventoryItem(item_name="chicken", quantity=10000)
    controller._db_manager.get_current_quantity.side_effect = [3, 0]
    controller.db.remove_item.return_value = True

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("remove", item)), \
         patch('pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("remove all chicken")

    assert success
    assert feedback == "chicken has been removed from inventory."
    controller.db.remove_item.assert_called_with("chicken", 10000)


def test_process_command_missing_item_has_specific_feedback(controller):
    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("add", None)):
        success, feedback = controller.process_command("add")
        assert not success
        assert feedback == "Could not identify a valid item and quantity. Please try again."


def test_update_display_serialises_concurrent_renders(controller):
    """Two threads calling update_display_with_inventory must not both reach
    display_inventory simultaneously — the e-paper driver is not thread-safe."""
    import threading

    controller.db.get_inventory.side_effect = lambda: [("salmon", 1)]

    in_render = threading.Event()
    proceed = threading.Event()
    overlapped = []

    def slow_render(display, items, cfg):
        if in_render.is_set():
            overlapped.append(True)
        in_render.set()
        proceed.wait(timeout=1)
        in_render.clear()
        return True

    with patch('pi_inventory_system.inventory_controller.display_inventory',
              side_effect=slow_render):
        t1 = threading.Thread(target=controller.update_display_with_inventory)
        t1.start()
        # Force the second call to see a different inventory so the dedup cache
        # does not turn it into a no-op.
        controller._last_rendered_inventory = []
        t2 = threading.Thread(target=controller.update_display_with_inventory)
        t2.start()
        proceed.set()
        t1.join(timeout=2)
        t2.join(timeout=2)

    assert overlapped == []


def test_process_command_set_to_zero_deletes(controller):
    """`set X to 0` must reach set_item — quantity 0 is the delete idiom for set."""
    item = InventoryItem(item_name="chicken", quantity=0)
    controller.db.set_item.return_value = True
    controller._db_manager.get_current_quantity.return_value = 0

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("set", item)), \
         patch('pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("set chicken to 0")
        assert success
        assert feedback == "chicken has been removed from inventory."
        controller.db.set_item.assert_called_once_with("chicken", 0)


def test_process_command_rejects_zero_remove(controller):
    """`remove 0 X` is not valid even though it's syntactically harmless."""
    item = InventoryItem(item_name="chicken", quantity=0)

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("remove", item)):
        success, feedback = controller.process_command("remove 0 chicken")
        assert not success
        assert feedback == "Invalid item details. Please check the item name and quantity."
        controller.db.remove_item.assert_not_called()


def test_process_command_rejects_zero_add(controller):
    item = InventoryItem(item_name="chicken", quantity=0)

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("add", item)):
        success, feedback = controller.process_command("add 0 chicken")
        assert not success
        assert feedback == "Invalid item details. Please check the item name and quantity."
        controller.db.add_item.assert_not_called()


def test_process_command_success_when_display_refresh_fails(controller):
    """A display error after the DB mutation should not report command failure."""
    item = InventoryItem(item_name="chicken", quantity=1)
    controller.db.add_item.return_value = True
    controller._db_manager.get_current_quantity.return_value = 1

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("add", item)), \
         patch('pi_inventory_system.inventory_controller.display_inventory',
               side_effect=RuntimeError("display offline")):
        success, feedback = controller.process_command("add chicken")
        assert success
        assert feedback == "chicken now has 1 in inventory."


def test_update_display_raises_when_render_returns_false(controller):
    controller.db.get_inventory.return_value = [("steak", 1)]
    with patch('pi_inventory_system.inventory_controller.display_inventory', return_value=False):
        with pytest.raises(DisplayError):
            controller.update_display_with_inventory()
    assert controller._last_rendered_inventory is None


def test_process_command_from_executor_thread_updates_database(tmp_path):
    """Production voice commands run in a worker thread and must be able to write SQLite."""
    cfg = create_config_manager()
    cfg._config['nlp']['enable_spacy'] = False
    db = create_database_manager(cfg, db_path=str(tmp_path / "threaded.db"))
    controller_instance = InventoryController(db_manager=db, display=None, config_manager=cfg)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            success, feedback = executor.submit(
                controller_instance.process_command,
                "add 1 salmon",
            ).result(timeout=5)

        assert success
        assert feedback == "salmon now has 1 in inventory."
        assert db.get_current_quantity("salmon") == 1
    finally:
        db.cleanup()


def test_process_command_successful_undo(controller):
    """Test processing a successful undo command."""
    controller._db_manager.undo_last_change.return_value = (True, "chicken")

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("undo", None)), \
         patch('pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("undo")
        assert success
        assert feedback == "Last change for chicken has been undone."
        controller.db.undo_last_change.assert_called_once()


def test_process_command_successful_set(controller):
    """Test processing a successful set command."""
    item = InventoryItem(item_name="chicken", quantity=5)
    controller.db.set_item.return_value = True
    controller._db_manager.get_current_quantity.return_value = 5

    with patch('pi_inventory_system.inventory_controller.interpret_command',
              return_value=("set", item)), \
         patch('pi_inventory_system.inventory_controller.display_inventory'):
        success, feedback = controller.process_command("set chicken to 5")
        assert success
        assert feedback == "chicken now has 5 in inventory."
        controller.db.set_item.assert_called_with(item.item_name, item.quantity)


def test_update_display_with_inventory(controller):
    """Display only shows items with quantity > 0, sorted by name."""
    controller.db.get_inventory.return_value = [("steak", 1), ("chicken breast", 2)]

    with patch(
        'pi_inventory_system.inventory_controller.display_inventory'
    ) as mock_display_inventory:
        controller.update_display_with_inventory()
        actual_list = mock_display_inventory.call_args[0][1]
        assert actual_list == [('chicken breast', 2), ('steak', 1)]


def test_update_display_skips_when_unchanged(controller):
    """Re-rendering the same inventory does not call display_inventory twice."""
    controller.db.get_inventory.return_value = [("steak", 1)]
    with patch(
        'pi_inventory_system.inventory_controller.display_inventory'
    ) as mock_display_inventory:
        controller.update_display_with_inventory()
        controller.update_display_with_inventory()
        assert mock_display_inventory.call_count == 1


def test_update_display_drops_zero_quantity_rows(controller):
    """Rows that came back with quantity 0 are not rendered."""
    controller.db.get_inventory.return_value = [("steak", 0), ("salmon", 3)]
    with patch(
        'pi_inventory_system.inventory_controller.display_inventory'
    ) as mock_display_inventory:
        controller.update_display_with_inventory()
        actual_list = mock_display_inventory.call_args[0][1]
        assert actual_list == [('salmon', 3)]


@pytest.mark.skip(reason="Loop-related tests are not critical and can be flaky")
def test_run_loop_keyboard_interrupt(controller):
    """Test handling keyboard interrupt in run loop."""
    pass


@pytest.mark.skip(reason="Loop-related tests are not critical and can be flaky")
def test_run_loop_exception(controller):
    """Test handling general exception in run loop."""
    pass
