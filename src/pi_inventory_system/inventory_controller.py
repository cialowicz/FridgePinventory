import logging
from typing import List, Tuple, Optional
from .database_manager import db_manager
from .command_processor import interpret_command
from .display_manager import initialize_display, display_inventory
from .inventory_item import InventoryItem


class InventoryController:
    """Controller class for managing the inventory system."""
    
    def __init__(self):
        """Initialize the inventory controller."""
        self._initialize_system()
        self._command_history: List[Tuple[str, InventoryItem]] = []
    
    def _initialize_system(self) -> None:
        """Initialize the database and display."""
        # Initialize database and display
        db_manager.initialize()
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
            
        success = self._execute_command(command_type, item)
        if not success:
            return False, "Command failed to execute. Please try again."
            
        # Get current inventory state for feedback
        inventory = db_manager.get_inventory()
        
        # Generate appropriate feedback message
        feedback = self._generate_feedback(command_type, item, inventory)
        
        # Update display
        display_inventory(self.display)
        
        return True, feedback
    
    def _generate_feedback(self, command_type: str, item: Optional[InventoryItem], inventory: List[Tuple[str, int]]) -> str:
        """Generate feedback message based on command type and current inventory.
        
        Args:
            command_type: Type of command executed
            item: The inventory item being modified
            inventory: Current inventory state
            
        Returns:
            Feedback message string
        """
        if command_type == "undo":
            last_item = None
            last_quantity = 0
            for inv_item_name, qty in inventory:
                if inv_item_name == item:  # item contains the item name for undo
                    last_item = inv_item_name
                    last_quantity = qty
                    break
            
            if last_item:
                if last_quantity == 0:
                    return f"Last change has been undone. {last_item} has been removed from inventory."
                return f"Last change has been undone. {last_item} now has {last_quantity} in inventory."
            return "Last change has been undone."
        
        # For other commands, get current quantity from inventory
        current_quantity = 0
        for inv_item_name, qty in inventory:
            if inv_item_name == item.item_name:
                current_quantity = qty
                break
        
        if current_quantity == 0:
            return f"{item.item_name} has been removed from inventory."
        return f"{item.item_name} now has {current_quantity} in inventory."
    
    def _execute_command(self, command_type: str, item: Optional[InventoryItem]) -> bool:
        """
        Execute a command based on its type and item.
        Returns True if successful, False otherwise.
        """
        if command_type == "undo":
            return db_manager.undo_last_change()
            
        if not command_type or not item:
            return False
            
        try:
            # Execute the command
            if command_type == "add":
                db_manager.add_item(item.item_name, item.quantity)
            elif command_type == "remove":
                db_manager.remove_item(item.item_name, item.quantity)
            elif command_type == "set":
                db_manager.set_item(item.item_name, item.quantity)
            else:
                return False
                
            # Add to command history
            self._command_history.append((command_type, item))
            return True
            
        except Exception as e:
            logging.error(f"Error executing command: {e}")
            return False
