import logging
import os
import time
import signal
import threading
import traceback
from typing import Optional, Tuple
from datetime import datetime, timedelta

# Import configuration first to get log level
from pi_inventory_system.config_manager import get_default_config_manager
from pi_inventory_system.database_manager import create_database_manager
from pi_inventory_system.diagnostics import run_startup_diagnostics
from pi_inventory_system.display_manager import initialize_display, display_inventory, cleanup_display
from pi_inventory_system.motion_sensor import detect_motion, cleanup
from pi_inventory_system.voice_recognition import recognize_speech_from_mic, cleanup_audio
from pi_inventory_system.inventory_controller import InventoryController
from pi_inventory_system.audio_feedback import AudioFeedback

# Try to import the new managers if available
try:
    from pi_inventory_system.motion_sensor_manager import MotionSensorManager
    from pi_inventory_system.voice_recognition_manager import VoiceRecognitionManager
    from pi_inventory_system.audio_feedback_manager import AudioFeedbackManager
    USE_NEW_MANAGERS = True
except ImportError:
    USE_NEW_MANAGERS = False

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
        
        # Use new managers if available
        if USE_NEW_MANAGERS:
            self.motion_manager = MotionSensorManager(config_manager=self.config_manager)
            self.voice_manager = VoiceRecognitionManager(config_manager=self.config_manager)
            self.audio_feedback = AudioFeedbackManager(config_manager=self.config_manager)
        else:
            self.motion_manager = None
            self.voice_manager = None
            self.audio_feedback = AudioFeedback()
        
        # Application state
        self.running = False
        self.shutdown_event = threading.Event()
        
        # Motion detection optimization
        self.last_motion_time = None
        self.motion_cooldown_seconds = 2  # Avoid rapid re-triggering
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
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
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating shutdown...")
        self.running = False
        self.shutdown_event.set()
    
    def run(self) -> None:
        """Run the main application loop with optimized motion detection."""
        if not self.initialize():
            self.logger.error("Failed to initialize application")
            return
        
        display_ok, motion_sensor_ok, audio_ok = self.hardware_status
        self.running = True
        
        try:
            # Display initial inventory on startup
            if display_ok:
                self.logger.info("Displaying initial inventory")
                self.controller.update_display_with_inventory()
            
            # Get configuration for loop timing
            system_config = self.config_manager.get_system_config()
            base_delay = system_config.get('main_loop_delay', 0.1)
            motion_check_interval = system_config.get('motion_check_interval', 0.5)
            idle_delay = system_config.get('idle_delay', 1.0)  # Longer delay when idle
            
            # Main loop
            motion_check_counter = 0
            last_motion_check = time.time()
            motion_active = False
            consecutive_no_motion = 0
            idle_mode = False
            
            while self.running and not self.shutdown_event.is_set():
                current_time = time.time()
                
                # Adaptive motion checking - check less frequently when idle
                check_interval = idle_delay if idle_mode else motion_check_interval
                
                if motion_sensor_ok and (current_time - last_motion_check) >= check_interval:
                    motion_check_counter += 1
                    last_motion_check = current_time
                    
                    # Log periodically, less frequently when idle
                    log_interval = 100 if idle_mode else 50
                    if motion_check_counter % log_interval == 0:
                        self.logger.debug(f"Motion check #{motion_check_counter}, idle_mode: {idle_mode}")
                    
                    # Check for motion with cooldown
                    motion_detected = False
                    if self.last_motion_time is None or \
                       (current_time - self.last_motion_time) > self.motion_cooldown_seconds:
                        if USE_NEW_MANAGERS and self.motion_manager:
                            motion_detected = self.motion_manager.detect_motion()
                        else:
                            motion_detected = detect_motion()
                    
                    if motion_detected:
                        self.logger.info("Motion detected")
                        self.last_motion_time = current_time
                        consecutive_no_motion = 0
                        idle_mode = False
                        
                        # Update display if transitioning from inactive to active
                        if not motion_active:
                            self.logger.info("Transitioning to active mode, updating display")
                            motion_active = True
                            if display_ok:
                                self.controller.update_display_with_inventory()
                        
                        # Start voice recognition in a separate thread with timeout
                        voice_thread = threading.Thread(
                            target=self._handle_voice_command,
                            args=(display_ok,)
                        )
                        voice_thread.daemon = True
                        voice_thread.start()
                        
                        # Wait for voice thread to complete or timeout
                        voice_thread.join(timeout=15)  # 15 second timeout
                        if voice_thread.is_alive():
                            self.logger.warning("Voice command timed out")
                    
                    else:
                        # No motion detected
                        if motion_active:
                            consecutive_no_motion += 1
                            # Require several consecutive no-motion checks before deactivating
                            if consecutive_no_motion >= 5:
                                self.logger.info("Motion ended, deactivating")
                                motion_active = False
                                consecutive_no_motion = 0
                        
                        # Enter idle mode after extended inactivity
                        if not motion_active and consecutive_no_motion == 0:
                            if not idle_mode and \
                               (self.last_motion_time is None or \
                                (current_time - self.last_motion_time) > 30):
                                self.logger.info("Entering idle mode")
                                idle_mode = True
                
                # Adaptive sleep based on activity
                if motion_active:
                    time.sleep(base_delay)  # Short delay when active
                elif idle_mode:
                    # Use interruptible sleep for idle mode
                    self.shutdown_event.wait(timeout=idle_delay)
                else:
                    time.sleep(motion_check_interval)  # Medium delay
                
        except Exception as e:
            self.logger.error(f"Unexpected error in main loop: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            self.logger.info("Shutting down...")
            self.running = False
            
            # Cleanup
            try:
                # Clean up managers if using new ones
                if USE_NEW_MANAGERS:
                    if self.motion_manager:
                        self.motion_manager.cleanup()
                    if self.voice_manager:
                        self.voice_manager.cleanup()
                    if hasattr(self.audio_feedback, 'cleanup'):
                        self.audio_feedback.cleanup()
                else:
                    cleanup()  # GPIO cleanup
                    cleanup_audio()  # Audio cleanup
                
                # Clean up display
                if self.display:
                    cleanup_display(self.display)
                
                # Clean up database if it has cleanup method
                if hasattr(self.db_manager, 'cleanup'):
                    self.db_manager.cleanup()
                
                self.logger.info("Cleanup complete")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")
    
    def _handle_voice_command(self, display_ok: bool) -> None:
        """Handle voice command in a separate thread."""
        try:
            if USE_NEW_MANAGERS and self.voice_manager:
                command = self.voice_manager.recognize_speech()
            else:
                command = recognize_speech_from_mic()
            
            if command and self.running:
                self.logger.info(f"Command received: {command}")
                
                # Process command
                success, feedback = self.controller.process_command(command)
                self.logger.info(f"Command result: {feedback}")
                
                # Update display
                if display_ok:
                    self.controller.update_display_with_inventory()
        except Exception as e:
            self.logger.error(f"Error handling voice command: {e}")

def main():
    """Main application entry point."""
    app = FridgePinventoryApp()
    app.run()

if __name__ == "__main__":
    main()
