# Module for system diagnostics

import time
import logging
from typing import Tuple
from pi_inventory_system.display_manager import initialize_display, display_text, is_display_supported
from pi_inventory_system.motion_sensor import detect_motion, is_motion_sensor_supported

def run_startup_diagnostics() -> Tuple[bool, bool]:
    """
    Run startup diagnostics and return status of display and motion sensor.
    Returns: (display_ok, motion_sensor_ok)
    """
    display_ok = False
    motion_sensor_ok = False
    
    # Check display
    if is_display_supported():
        display = initialize_display()
        if display:
            # Try to display startup message
            if display_text(display, "FridgePinventory\nstarting up..."):
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
    
    return display_ok, motion_sensor_ok 