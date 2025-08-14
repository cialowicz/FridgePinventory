import logging
from typing import List, Tuple, Optional
from .database_manager import get_default_db_manager
from .command_processor import interpret_command
from .display_manager import initialize_display, display_inventory
from .inventory_item import InventoryItem


class InventoryController:
    """Controller class for managing the inventory system."""
    
    def __init__(self, db_manager=None):
        """Initialize the inventory controller.
        
        Args:
            db_manager: Database manager instance. If None, uses default.
        """
        self._db_manager = db_manager or get_default_db_manager()
        self._initialize_system()
        self._command_history: List[Tuple[str, InventoryItem]] = []
    
    def _initialize_system(self) -> None:
        """Initialize the database and display."""
        # Database is already initialized in constructor
        self.display = initialize_display()
        if self.display:
            logging.info("Display initialized successfully")
        else:
            logging.warning("Display initialization failed or not supported")
    
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
            
        success, undo_item_name = self._execute_command(command_type, item)
        if not success:
            return False, "Command failed to execute. Please try again."
            
        # Get current inventory state for feedback
        inventory = self._db_manager.get_inventory()
        
        # Generate appropriate feedback message
        feedback = self._generate_feedback(command_type, item, inventory, undo_item_name)
        
        # Update display
        display_inventory(self.display)
        
        return True, feedback
    
    def _generate_feedback(self, command_type: str, item: Optional[InventoryItem], inventory: List[Tuple[str, int]], undo_item_name: Optional[str] = None) -> str:
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
            if not undo_item_name:
                return "Last change has been undone."
                
            # Find current quantity of the undone item
            current_quantity = 0
            for inv_item_name, qty in inventory:
                if inv_item_name == undo_item_name:
                    current_quantity = qty
                    break
            
            if current_quantity == 0:
                return f"Last change has been undone. {undo_item_name} has been removed from inventory."
            return f"Last change has been undone. {undo_item_name} now has {current_quantity} in inventory."
        
        # For other commands, get current quantity from inventory
        if not item:
            return "Command executed successfully."
            
        current_quantity = 0
        for inv_item_name, qty in inventory:
            if inv_item_name == item.item_name:
                current_quantity = qty
                break
        
        if current_quantity == 0:
            return f"{item.item_name} has been removed from inventory."
        return f"{item.item_name} now has {current_quantity} in inventory."
    
    def _execute_command(self, command_type: str, item: Optional[InventoryItem]) -> Tuple[bool, Optional[str]]:
        """
        Execute a command based on its type and item.
        Returns tuple of (success, undo_item_name) where undo_item_name is only set for undo operations.
        """
        if command_type == "undo":
            success, undo_item_name = self._db_manager.undo_last_change()
            return success, undo_item_name
            
        if not command_type or not item:
            return False, None
            
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
                # Add to command history
                self._command_history.append((command_type, item))
                return True, None
            else:
                return False, None
                
        except Exception as e:
            logging.error(f"Error executing command: {e}")
            return False, None
