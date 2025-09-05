import logging
from typing import List, Tuple, Optional
from .database_manager import get_default_db_manager
from .command_processor import interpret_command
from .display_manager import display_inventory
from .item_normalizer import ITEM_SYNONYMS, normalize_item_name
from .inventory_item import InventoryItem
from .exceptions import InventoryError, CommandProcessingError


class InventoryController:
    """Controller class for managing the inventory system."""
    
    def __init__(self, db_manager=None, display=None):
        """Initialize the inventory controller.
        
        Args:
            db_manager: Database manager instance. If None, uses default.
            display: Display instance. If None, display features will be disabled.
        """
        self._db_manager = db_manager or get_default_db_manager()
        self.display = display
        self._command_history: List[Tuple[str, InventoryItem]] = []
        
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
            command_type, item = interpret_command(command)
            if not command_type:
                return False, "Command not recognized. Please try again with add, remove, set, or undo."
            
            # Validate item if present
            if item and command_type != "undo":
                if not self._validate_item(item):
                    return False, "Invalid item details. Please check the item name and quantity."
            
            success, new_quantity, undo_item_name = self._execute_command(command_type, item)
            if not success:
                return False, "Command failed to execute. Please check inventory and try again."

            # Generate appropriate feedback message
            feedback = self._generate_feedback(command_type, item, new_quantity, undo_item_name)
            
            # Update display
            self.update_display_with_inventory()
            
            return True, feedback
            
        except CommandProcessingError as e:
            logging.error(f"Command processing error: {e}")
            return False, str(e)
        except Exception as e:
            logging.error(f"Unexpected error processing command: {e}")
            return False, "An unexpected error occurred. Please try again."

    def update_display_with_inventory(self):
        """Fetch inventory, merge with all categories, and update the display."""
        if not self.display:
            return
        try:
            # Get the actual inventory from the database and convert to a dict for easy lookup
            db_inventory_list = self._db_manager.get_inventory()
            db_inventory = dict(db_inventory_list)

            # Get all possible item categories from the normalizer
            all_categories = list(ITEM_SYNONYMS.keys())

            # Create a comprehensive list, showing 0 for items not in the database inventory
            display_list = []
            for category in sorted(all_categories):
                quantity = db_inventory.get(category, 0)
                display_list.append((category, quantity))

            # Call the display function with the complete, sorted list
            display_inventory(self.display, display_list)
            logging.info(f"Updated display with {len(display_list)} items.")
        except Exception as e:
            logging.error(f"Failed to update display with inventory: {e}")
    
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
        """
        Execute a command based on its type and item.
        Returns tuple of (success, new_quantity, undo_item_name) where undo_item_name is only set for undo operations.
        """
        if command_type == "undo":
            try:
                success, undo_item_name = self._db_manager.undo_last_change()
                if success and undo_item_name:
                    # Get the new quantity for the undone item
                    new_quantity = self._db_manager.get_current_quantity(undo_item_name)
                    return success, new_quantity, undo_item_name
                return success, None, undo_item_name
            except Exception as e:
                logging.error(f"Error executing undo: {e}")
                return False, None, None

        if not command_type or not item:
            logging.warning(f"Missing command type or item: type={command_type}, item={item}")
            return False, None, None

        try:
            # Normalize item name before execution
            original_name = item.item_name
            item.item_name = normalize_item_name(item.item_name) or item.item_name
            
            # Log the operation
            logging.info(f"Executing {command_type} for {item.item_name} (qty: {item.quantity})")
            
            # Execute the command with validation
            success = False
            if command_type == "add":
                # Check for reasonable limits
                current_qty = self._db_manager.get_current_quantity(item.item_name)
                if current_qty + item.quantity > 10000:
                    logging.warning(f"Adding would exceed maximum quantity for {item.item_name}")
                    raise InventoryError(f"Cannot add {item.quantity} - would exceed maximum of 10000")
                success = self._db_manager.add_item(item.item_name, item.quantity)
                
            elif command_type == "remove":
                # Check if enough items exist
                current_qty = self._db_manager.get_current_quantity(item.item_name)
                if current_qty < item.quantity:
                    logging.info(f"Removing {item.quantity} but only {current_qty} available")
                    # Allow partial removal
                success = self._db_manager.remove_item(item.item_name, item.quantity)
                
            elif command_type == "set":
                # Direct set with validation already done
                success = self._db_manager.set_item(item.item_name, item.quantity)
            else:
                logging.error(f"Unknown command type: {command_type}")
                return False, None, None

            if success:
                # Get the new quantity
                new_quantity = self._db_manager.get_current_quantity(item.item_name)
                # Add to command history (limit size)
                self._command_history.append((command_type, item))
                if len(self._command_history) > 100:  # Keep last 100 commands
                    self._command_history = self._command_history[-100:]
                return True, new_quantity, None
            else:
                logging.warning(f"Command {command_type} failed for {item.item_name}")
                return False, None, None

        except InventoryError as e:
            logging.error(f"Inventory error: {e}")
            raise CommandProcessingError(str(e))
        except Exception as e:
            logging.error(f"Unexpected error executing command: {e}")
            return False, None, None
