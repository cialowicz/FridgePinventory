import logging
from typing import List, Tuple, Optional
from .database_manager import get_default_db_manager
from .command_processor import interpret_command
from .display_manager import display_inventory
from .inventory_item import InventoryItem


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
        if not command:
            return False, "Could not understand audio. Please try again."
            
        command_type, item = interpret_command(command)
        if not command_type:
            return False, "Command not recognized. Please try again with a valid command."
            
        success, new_quantity, undo_item_name = self._execute_command(command_type, item)
        if not success:
            return False, "Command failed to execute. Please try again."

        # Generate appropriate feedback message
        feedback = self._generate_feedback(command_type, item, new_quantity, undo_item_name)
        
        # Update display
        self.update_display_with_inventory()
        
        return True, feedback

    def update_display_with_inventory(self):
        """Fetch inventory and update the display."""
        if not self.display:
            return
        try:
            inventory = self._db_manager.get_inventory()
            display_inventory(self.display, inventory)
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
    
    def _execute_command(self, command_type: str, item: Optional[InventoryItem]) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Execute a command based on its type and item.
        Returns tuple of (success, new_quantity, undo_item_name) where undo_item_name is only set for undo operations.
        """
        if command_type == "undo":
            success, undo_item_name = self._db_manager.undo_last_change()
            return success, None, undo_item_name

        if not command_type or not item:
            return False, None, None

        try:
            # Execute the command
            success = False
            if command_type == "add":
                success = self._db_manager.add_item(item.item_name, item.quantity)
            elif command_type == "remove":
                success = self._db_manager.remove_item(item.item_name, item.quantity)
            elif command_type == "set":
                success = self._db_manager.set_item(item.item_name, item.quantity)

            if success:
                # Get the new quantity
                new_quantity = self._db_manager.get_current_quantity(item.item_name)
                # Add to command history
                self._command_history.append((command_type, item))
                return True, new_quantity, None
            else:
                return False, None, None

        except Exception as e:
            logging.error(f"Error executing command: {e}")
            return False, None, None
