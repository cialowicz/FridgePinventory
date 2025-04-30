# Main entry point for the application

import os
import time
import logging
from pathlib import Path
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


def main():
    """Main function to run the inventory system."""
    # Initialize the database
    init_db()
    
    # Initialize the display
    initialize_display()
    
    while True:
        try:
            # Wait for motion detection
            if detect_motion():
                # Get voice command
                command = recognize_speech_from_mic()
                if command:
                    # Process command
                    command_type, details = interpret_command(command)
                    if command_type:
                        success = execute_command(command_type, details)
                        play_feedback_sound(success)
                        if success:
                            # Get current inventory state for feedback
                            inventory = get_inventory()
                            if command_type == "undo":
                                # Get the last affected item and its new quantity
                                last_item = None
                                last_quantity = 0
                                for item, qty in inventory:
                                    if item == details:  # details contains the item name for undo
                                        last_item = item
                                        last_quantity = qty
                                        break
                                
                                if last_item:
                                    if last_quantity == 0:
                                        output_confirmation(f"Last change has been undone. {last_item} has been removed from inventory.")
                                    else:
                                        output_confirmation(f"Last change has been undone. {last_item} now has {last_quantity} in inventory.")
                                else:
                                    output_confirmation("Last change has been undone.")
                            else:
                                if command_type == "set":
                                    item_name, quantity = details
                                else:
                                    quantity, item_name = details
                                
                                # Find the item in inventory
                                current_quantity = 0
                                for item, qty in inventory:
                                    if item == item_name:
                                        current_quantity = qty
                                        break
                                
                                if current_quantity == 0:
                                    output_confirmation(f"{item_name} has been removed from inventory.")
                                else:
                                    output_confirmation(f"{item_name} now has {current_quantity} in inventory.")
                            
                            # Update display
                            display_inventory(inventory)
                        else:
                            output_confirmation("Command failed to execute. Please try again.")
                    else:
                        play_feedback_sound(False)
                        output_confirmation("Command not recognized. Please try again with a valid command.")
                else:
                    play_feedback_sound(False)
                    output_confirmation("Could not understand audio. Please try again.")
            
            # Small delay to prevent CPU overuse
            time.sleep(0.1)
            
        except KeyboardInterrupt:
            print("\nShutting down...")
            break
        except Exception as e:
            print(f"Error: {e}")
            play_feedback_sound(False)
            output_confirmation("An error occurred.")


if __name__ == "__main__":
    main()
