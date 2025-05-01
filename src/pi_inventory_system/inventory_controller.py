import logging
import time
from typing import List, Tuple, Optional, Dict, Any
from .inventory_db import (
    init_db,
    add_item,
    remove_item,
    set_item,
    get_inventory
)
from .motion_sensor import detect_motion
from .voice_recognition import recognize_speech_from_mic
from .command_processor import interpret_command, execute_command
from .display_manager import initialize_display, display_inventory
from .audio_feedback import play_feedback_sound, output_confirmation
from .inventory_item import InventoryItem


class InventoryController:
    """Controller class for managing the inventory system."""
    
    def __init__(self):
        """Initialize the inventory controller."""
        self._initialize_system()
    
    def _initialize_system(self) -> None:
        """Initialize the database and display."""
        init_db()
        initialize_display()
    
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
            
        success = execute_command(command_type, item)
        if not success:
            return False, "Command failed to execute. Please try again."
            
        # Get current inventory state for feedback
        inventory = get_inventory()
        
        # Generate appropriate feedback message
        feedback = self._generate_feedback(command_type, item, inventory)
        
        # Update display
        display_inventory(inventory)
        
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
    
    def run_loop(self) -> None:
        """Run the main control loop."""
        while True:
            try:
                if detect_motion():
                    command = recognize_speech_from_mic()
                    success, feedback = self.process_command(command)
                    play_feedback_sound(success)
                    output_confirmation(feedback)
                
                # Small delay to prevent CPU overuse
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                logging.info("Shutting down...")
                break
            except Exception as e:
                logging.error(f"Error: {e}")
                play_feedback_sound(False)
                output_confirmation("An error occurred.") 