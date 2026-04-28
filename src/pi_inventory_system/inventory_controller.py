import logging
from typing import List, Tuple, Optional
from .database_manager import get_default_db_manager
from .command_processor import interpret_command
from .display_manager import display_inventory
from .item_normalizer import normalize_item_name
from .inventory_item import InventoryItem
from .exceptions import CommandProcessingError, DatabaseError, InventoryError


class InventoryController:
    """Controller class for managing the inventory system."""
    
    def __init__(self, db_manager=None, display=None, config_manager=None):
        """Initialize the inventory controller.

        Args:
            db_manager: Database manager instance. If None, uses default.
            display: Display instance. If None, display features will be disabled.
        """
        self._db_manager = db_manager or get_default_db_manager()
        self.display = display
        self.config_manager = config_manager
        self._command_history: List[Tuple[str, InventoryItem]] = []
        self._last_rendered_inventory: Optional[List[Tuple[str, int]]] = None

        if self.display:
            logging.info("Display instance provided to InventoryController")
        else:
            logging.warning("No display instance provided - display features disabled")
    

    
    def process_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """Process a voice command and return success status and feedback message.
        
        Args:
            command: The voice command to process
            
        Returns:
            Tuple of (success, feedback_message)
        """
        # Input validation
        if not command:
            return False, "Could not understand audio. Please try again."
        
        if not isinstance(command, str):
            logging.error(f"Invalid command type: {type(command)}")
            return False, "Invalid command format."
        
        if len(command) > 500:
            logging.warning(f"Command too long: {len(command)} characters")
            return False, "Command too long. Please use shorter commands."
        
        try:
            command_type, item = interpret_command(command, self.config_manager)
            if not command_type:
                return False, "Command not recognized. Please try again with add, remove, set, or undo."
            
            # Validate item if present
            if item and command_type != "undo":
                if not self._validate_item(item):
                    return False, "Invalid item details. Please check the item name and quantity."
            
            success, new_quantity, status_item_name = self._execute_command(command_type, item)
            if not success:
                if command_type == "remove" and status_item_name:
                    return False, f"{status_item_name} is not in inventory."
                return False, "Command failed to execute. Please check inventory and try again."

            # Generate appropriate feedback message
            feedback = self._generate_feedback(command_type, item, new_quantity, status_item_name)
            
            # Update display
            try:
                self.update_display_with_inventory()
            except Exception as e:
                logging.error(f"Inventory updated but display refresh failed: {e}")
            
            return True, feedback
            
        except CommandProcessingError as e:
            logging.error(f"Command processing error: {e}")
            return False, str(e)
        except Exception as e:
            logging.error(f"Unexpected error processing command: {e}")
            return False, "An unexpected error occurred. Please try again."

    def update_display_with_inventory(self):
        """Fetch inventory and refresh the display. Only items with quantity>0
        are shown; if the inventory is unchanged since the last render, the
        ~3.5s e-paper refresh is skipped."""
        if not self.display:
            return
        try:
            db_inventory_list = sorted(self._db_manager.get_inventory())
            display_list = [(name, qty) for name, qty in db_inventory_list if qty > 0]

            if display_list == self._last_rendered_inventory:
                logging.debug("Inventory unchanged since last render; skipping refresh")
                return

            display_inventory(self.display, display_list, self.config_manager)
            self._last_rendered_inventory = display_list
            logging.info(f"Updated display with {len(display_list)} items.")
        except Exception as e:
            logging.error(f"Failed to update display with inventory: {e}")
            raise
    
    def _generate_feedback(self, command_type: str, item: Optional[InventoryItem], new_quantity: Optional[int], undo_item_name: Optional[str] = None) -> str:
        """Generate feedback message based on command type and current inventory.
        
        Args:
            command_type: Type of command executed
            item: The inventory item being modified (None for undo)
            inventory: Current inventory state
            undo_item_name: Item name affected by undo operation
            
        Returns:
            Feedback message string
        """
        if command_type == "undo":
            return f"Last change has been undone."

        if item and new_quantity is not None:
            if new_quantity == 0:
                return f"{item.item_name} has been removed from inventory."
            else:
                return f"{item.item_name} now has {new_quantity} in inventory."

        return "Command executed successfully."
    
    def _validate_item(self, item: InventoryItem) -> bool:
        """Validate inventory item before processing.
        
        Args:
            item: Item to validate
            
        Returns:
            True if item is valid
        """
        if not item:
            return False
        
        # Validate item name
        if not item.item_name or len(item.item_name) < 1:
            logging.warning(f"Invalid item name: {item.item_name}")
            return False
        
        if len(item.item_name) > 100:
            logging.warning(f"Item name too long: {len(item.item_name)} characters")
            return False
        
        # Validate quantity
        if not isinstance(item.quantity, int):
            logging.warning(f"Invalid quantity type: {type(item.quantity)}")
            return False
        
        if item.quantity < 0:
            logging.warning(f"Negative quantity: {item.quantity}")
            return False
        
        if item.quantity > 10000:
            logging.warning(f"Quantity too large: {item.quantity}")
            return False
        
        return True
    
    def _execute_command(self, command_type: str, item: Optional[InventoryItem]) -> Tuple[bool, Optional[int], Optional[str]]:
        """Execute a command and return (success, new_quantity, affected_item_name)."""
        if command_type == "undo":
            try:
                success, undo_item_name = self._db_manager.undo_last_change()
            except DatabaseError as e:
                logging.error(f"Undo failed at the storage layer: {e}")
                return False, None, None
            if success and undo_item_name:
                return True, self._db_manager.get_current_quantity(undo_item_name), undo_item_name
            return success, None, undo_item_name

        if not command_type or not item:
            logging.warning(f"Missing command type or item: type={command_type}, item={item}")
            return False, None, None

        # Normalise without mutating the caller's InventoryItem.
        normalized_name = normalize_item_name(item.item_name, self.config_manager) or item.item_name
        normalized = InventoryItem(item_name=normalized_name, quantity=item.quantity)
        logging.info(f"Executing {command_type} for {normalized.item_name} (qty: {normalized.quantity})")

        try:
            if command_type == "add":
                current_qty = self._db_manager.get_current_quantity(normalized.item_name)
                if current_qty + normalized.quantity > 10000:
                    raise InventoryError(
                        f"Cannot add {normalized.quantity} - would exceed maximum of 10000")
                success = self._db_manager.add_item(normalized.item_name, normalized.quantity)
            elif command_type == "remove":
                current_qty = self._db_manager.get_current_quantity(normalized.item_name)
                if current_qty <= 0:
                    return False, 0, normalized.item_name
                success = self._db_manager.remove_item(normalized.item_name, normalized.quantity)
            elif command_type == "set":
                success = self._db_manager.set_item(normalized.item_name, normalized.quantity)
            else:
                logging.error(f"Unknown command type: {command_type}")
                return False, None, None
        except DatabaseError as e:
            logging.error(f"Storage failure during {command_type}: {e}")
            return False, None, None
        except InventoryError as e:
            raise CommandProcessingError(str(e))

        if not success:
            logging.warning(f"Command {command_type} reported failure for {normalized.item_name}")
            return False, None, None

        new_quantity = self._db_manager.get_current_quantity(normalized.item_name)
        self._command_history.append((command_type, normalized))
        if len(self._command_history) > 100:
            self._command_history = self._command_history[-100:]
        return True, new_quantity, None
