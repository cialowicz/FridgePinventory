# Module for system diagnostics

import time
import logging
from typing import Tuple
from pi_inventory_system.display_manager import initialize_display, display_text, is_display_supported
from pi_inventory_system.motion_sensor import detect_motion, is_motion_sensor_supported
from .audio_feedback_manager import AudioFeedbackManager

def run_startup_diagnostics(config_manager) -> Tuple[bool, bool, bool, object]:
    """
    Run startup diagnostics and return status of display, motion sensor, and audio.
    Returns: (display_ok, motion_sensor_ok, audio_ok, display_instance)
    """
    display_ok = False
    motion_sensor_ok = False
    audio_ok = False
    display = None
    
    # Check display
    if is_display_supported(config_manager):
        display = initialize_display(config_manager)
        if display:
            # Try to display startup message
            if display_text(display, "FridgePinventory\nstarting up...", config_manager=config_manager):
                display_ok = True
                logging.info("Display initialized successfully")
            else:
                logging.error("Failed to display startup message")
        else:
            logging.error("Failed to initialize display")
    else:
        logging.warning("Display not supported on this platform")
    
    # Wait a moment for display to update
    time.sleep(2)
    
    # Check motion sensor
    if is_motion_sensor_supported():
        # Try to detect motion
        try:
            # Read the sensor a few times to ensure it's working
            readings = [detect_motion() for _ in range(3)]
            motion_sensor_ok = True
            logging.info("Motion sensor initialized successfully")
            logging.info(f"Initial motion sensor readings: {readings}")
        except Exception as e:
            logging.error(f"Motion sensor error: {e}")
    else:
        logging.warning("Motion sensor not supported on this platform")
    
    # Check audio
    audio_manager = AudioFeedbackManager(config_manager=config_manager)
    try:
        if audio_manager.play_sound('success'):
            logging.info("Audio feedback sound played successfully.")
            audio_ok = True
        else:
            logging.warning("Failed to play audio feedback sound.")
            audio_ok = False
    except Exception as e:
        logging.error(f"Audio diagnostics failed: {e}")
        audio_ok = False
    finally:
        audio_manager.cleanup()
    
    # Final status display
    if display_ok and display:
        status_text = "Diagnostics complete:\n"
        status_text += f"Display: {'OK' if display_ok else 'FAIL'}\n"
        status_text += f"Motion: {'OK' if motion_sensor_ok else 'FAIL'}\n"
        status_text += f"Audio: {'OK' if audio_ok else 'FAIL'}"
        display_text(display, status_text, config_manager=config_manager)
    
    return display_ok, motion_sensor_ok, audio_ok, display
