# Main application entry point

import logging
from pi_inventory_system.diagnostics import run_startup_diagnostics
from pi_inventory_system.display_manager import initialize_display, display_inventory
from pi_inventory_system.motion_sensor import detect_motion, cleanup
from pi_inventory_system.voice_recognition import recognize_speech_from_mic
from pi_inventory_system.command_processor import interpret_command, execute_command
from pi_inventory_system.inventory_controller import InventoryController
import time

def main():
    """Main application loop."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logging.info("Starting FridgePinventory...")
    
    # Run startup diagnostics
    display_ok, motion_sensor_ok = run_startup_diagnostics()
    
    if not display_ok:
        logging.error("Display initialization failed. Some features may not work.")
    
    if not motion_sensor_ok:
        logging.error("Motion sensor initialization failed. Some features may not work.")
    
    # Initialize display
    display = initialize_display()
    
    # Initialize inventory controller
    controller = InventoryController()
    
    try:
        # Main loop
        while True:
            # Check for motion
            if motion_sensor_ok and detect_motion():
                logging.info("Motion detected")
                
                # Display current inventory
                display_inventory(display)
                
                # Wait for voice command
                command = recognize_speech_from_mic()
                if command:
                    logging.info(f"Command received: {command}")
                    
                    # Process command
                    success, feedback = controller.process_command(command)
                    logging.info(f"Command result: {feedback}")
                    
                    # Update display
                    display_inventory(display)
            
            # Small delay to prevent CPU hogging
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        # Cleanup
        cleanup()
        logging.info("Cleanup complete")

if __name__ == "__main__":
    main()
