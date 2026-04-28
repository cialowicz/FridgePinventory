# Module for system diagnostics

import logging
import time
from typing import Tuple

from .audio_feedback_manager import AudioFeedbackManager
from .display_manager import display_text, initialize_display, is_display_supported
from .motion_sensor_manager import MotionSensorManager


def run_startup_diagnostics(config_manager) -> Tuple[bool, bool, bool, object]:
    """Run startup diagnostics.

    Returns: (display_ok, motion_sensor_ok, audio_ok, display_instance)
    """
    display_ok = False
    motion_sensor_ok = False
    audio_ok = False
    display = None

    if is_display_supported(config_manager):
        display = initialize_display(config_manager)
        if display:
            if display_text(display, "FridgePinventory\nstarting up...", config_manager=config_manager):
                display_ok = True
                logging.info("Display initialized successfully")
            else:
                logging.error("Failed to display startup message")
        else:
            logging.error("Failed to initialize display")
    else:
        logging.warning("Display not supported on this platform")

    time.sleep(2)

    motion_manager = MotionSensorManager(config_manager=config_manager)
    if motion_manager.is_supported():
        try:
            readings = [motion_manager.detect_motion() for _ in range(3)]
            motion_sensor_ok = True
            logging.info("Motion sensor initialized successfully")
            logging.info(f"Initial motion sensor readings: {readings}")
        except Exception as e:
            logging.error(f"Motion sensor error: {e}")
    else:
        logging.warning("Motion sensor not supported on this platform")

    audio_manager = AudioFeedbackManager(config_manager=config_manager)
    try:
        if audio_manager.play_sound('success'):
            logging.info("Audio feedback sound played successfully.")
            audio_ok = True
        else:
            logging.warning("Failed to play audio feedback sound.")
    except Exception as e:
        logging.error(f"Audio diagnostics failed: {e}")
    finally:
        audio_manager.cleanup()

    if display_ok and display:
        status_text = (
            "Diagnostics complete:\n"
            f"Display: {'OK' if display_ok else 'FAIL'}\n"
            f"Motion: {'OK' if motion_sensor_ok else 'FAIL'}\n"
            f"Audio: {'OK' if audio_ok else 'FAIL'}"
        )
        display_text(display, status_text, config_manager=config_manager)

    return display_ok, motion_sensor_ok, audio_ok, display
