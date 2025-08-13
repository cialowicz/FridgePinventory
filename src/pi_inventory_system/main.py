import logging
import os

# Import configuration first to get log level
from pi_inventory_system.config_manager import config

# Setup basic logging with configurable level
system_config = config.get_system_config()
log_level = getattr(logging, system_config.get('log_level', 'INFO').upper(), logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(pathname)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler() # This will go to journald via systemd
        # Optionally, add a FileHandler if direct file logging is also desired for local debugging
        # logging.FileHandler("/tmp/fridgepinventory_debug.log")
    ]
)
logger = logging.getLogger(__name__)

logger.info(f"Application starting. User: {os.getenv('USER', 'N/A')}, Home: {os.getenv('HOME', 'N/A')}")
logger.debug("DEBUG logging enabled.")

from pi_inventory_system.diagnostics import run_startup_diagnostics
from pi_inventory_system.display_manager import initialize_display, display_inventory
from pi_inventory_system.motion_sensor import detect_motion, cleanup
from pi_inventory_system.voice_recognition import recognize_speech_from_mic
from pi_inventory_system.command_processor import interpret_command, execute_command
from pi_inventory_system.inventory_controller import InventoryController
from pi_inventory_system.config_manager import config
import time

def main():
    """Main application loop."""
    
    logger.info("Starting FridgePinventory...")
    
    # Run startup diagnostics
    display_ok, motion_sensor_ok, audio_ok = run_startup_diagnostics()
    
    if not display_ok:
        logger.error("Display initialization failed. Some features may not work.")
    
    if not motion_sensor_ok:
        logger.error("Motion sensor initialization failed. Some features may not work.")
        
    if not audio_ok:
        logger.error("Audio initialization failed. Some features may not work.")
    
    # Initialize display
    display = initialize_display()
    
    # Initialize inventory controller
    controller = InventoryController()
    
    try:
        # Main loop
        while True:
            # Check for motion
            if motion_sensor_ok and detect_motion():
                logger.info("Motion detected")
                
                # Display current inventory
                display_inventory(display)
                
                # Wait for voice command
                command = recognize_speech_from_mic()
                if command:
                    logger.info(f"Command received: {command}")
                    
                    # Process command
                    success, feedback = controller.process_command(command)
                    logger.info(f"Command result: {feedback}")
                    
                    # Update display
                    display_inventory(display)
            
            # Small delay to prevent CPU hogging (configurable)
            system_config = config.get_system_config()
            delay = system_config.get('main_loop_delay', 0.1)
            time.sleep(delay)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        # Cleanup
        cleanup()
        logger.info("Cleanup complete")

if __name__ == "__main__":
    main()
