import logging
import os
import time
from typing import Optional, Tuple

# Import configuration first to get log level
from pi_inventory_system.config_manager import get_default_config_manager
from pi_inventory_system.database_manager import create_database_manager
from pi_inventory_system.diagnostics import run_startup_diagnostics
from pi_inventory_system.display_manager import initialize_display, display_inventory
from pi_inventory_system.motion_sensor import detect_motion, cleanup
from pi_inventory_system.voice_recognition import recognize_speech_from_mic
from pi_inventory_system.inventory_controller import InventoryController
from pi_inventory_system.audio_feedback import AudioFeedback

class FridgePinventoryApp:
    """Main application class for FridgePinventory system."""
    
    def __init__(self, config_path: Optional[str] = None, db_path: Optional[str] = None):
        """Initialize the application.
        
        Args:
            config_path: Path to configuration file. If None, uses default.
            db_path: Path to database file. If None, uses config default.
        """
        # Initialize configuration and database managers
        self.config_manager = get_default_config_manager() if config_path is None else get_default_config_manager()
        self.db_manager = create_database_manager(db_path)
        
        # Initialize logging
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.controller = None
        self.display = None
        self.hardware_status = None
        self.audio_feedback = AudioFeedback()
        
        self.logger.info(f"Application starting. User: {os.getenv('USER', 'N/A')}, Home: {os.getenv('HOME', 'N/A')}")
        self.logger.debug("DEBUG logging enabled.")
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        system_config = self.config_manager.get_system_config()
        log_level = getattr(logging, system_config.get('log_level', 'INFO').upper(), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - [%(pathname)s:%(lineno)d] - %(message)s',
            handlers=[
                logging.StreamHandler()  # This will go to journald via systemd
                # Optionally, add a FileHandler if direct file logging is also desired for local debugging
                # logging.FileHandler("/tmp/fridgepinventory_debug.log")
            ]
        )
    
    def initialize(self) -> bool:
        """Initialize all system components.
        
        Returns:
            True if initialization successful, False otherwise
        """
        self.logger.info("Starting FridgePinventory initialization...")
        
        # Run startup diagnostics and get display instance
        display_ok, motion_sensor_ok, audio_ok, display_instance = self._run_diagnostics()
        self.hardware_status = (display_ok, motion_sensor_ok, audio_ok)
        
        # Use display instance from diagnostics to avoid GPIO conflicts
        self.display = display_instance
        if not self.display and display_ok:
            self.logger.warning("Display reported OK but no instance returned, attempting to initialize...")
            self.display = initialize_display()
        
        # Initialize inventory controller with our database manager and display instance
        self.controller = InventoryController(self.db_manager, self.display)

        # Play startup sound
        if audio_ok:
            self.logger.info("Playing startup sound.")
            self.audio_feedback.play_sound('success')
        
        self.logger.info("FridgePinventory initialization complete")
        return True
    
    def _run_diagnostics(self) -> Tuple[bool, bool, bool, object]:
        """Run startup diagnostics and log results.
        
        Returns:
            Tuple of (display_ok, motion_sensor_ok, audio_ok, display_instance)
        """
        display_ok, motion_sensor_ok, audio_ok, display_instance = run_startup_diagnostics()
        
        if not display_ok:
            self.logger.error("Display initialization failed. Some features may not work.")
        
        if not motion_sensor_ok:
            self.logger.error("Motion sensor initialization failed. Some features may not work.")
            
        if not audio_ok:
            self.logger.error("Audio initialization failed. Some features may not work.")
        
        return display_ok, motion_sensor_ok, audio_ok, display_instance
    
    def run(self) -> None:
        """Run the main application loop."""
        if not self.initialize():
            self.logger.error("Failed to initialize application")
            return
        
        display_ok, motion_sensor_ok, audio_ok = self.hardware_status
        
        try:
            # Display initial inventory on startup
            if display_ok:
                self.logger.info("Displaying initial inventory")
                self.controller.update_display_with_inventory()
            
            # Main loop
            motion_check_counter = 0
            motion_detected_in_cycle = False
            while True:
                # Check for motion
                motion_check_counter += 1
                if motion_check_counter % 50 == 0:  # Log every 50 iterations (about every 5 seconds)
                    self.logger.debug(f"Motion sensor check #{motion_check_counter}, motion_sensor_ok: {motion_sensor_ok}")
                
                if motion_sensor_ok and detect_motion():
                    self.logger.info("Motion detected")
                    
                    # On first detection, update the display
                    if not motion_detected_in_cycle:
                        self.logger.info("Motion detected, updating display.")
                        self.controller.update_display_with_inventory()
                        motion_detected_in_cycle = True
                    
                    # Wait for voice command
                    command = recognize_speech_from_mic()
                    if command:
                        self.logger.info(f"Command received: {command}")
                        
                        # Process command
                        success, feedback = self.controller.process_command(command)
                        self.logger.info(f"Command result: {feedback}")
                        
                        # Update display
                        self.controller.update_display_with_inventory()
                
                else:
                    # Reset motion detection flag when no motion is detected
                    if motion_detected_in_cycle:
                        self.logger.info("Motion ended, resetting cycle.")
                        motion_detected_in_cycle = False

                # Small delay to prevent CPU hogging (configurable)
                system_config = self.config_manager.get_system_config()
                delay = system_config.get('main_loop_delay', 0.1)
                time.sleep(delay)
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
        finally:
            # Cleanup
            cleanup()
            self.logger.info("Cleanup complete")

def main():
    """Main application entry point."""
    app = FridgePinventoryApp()
    app.run()

if __name__ == "__main__":
    main()
