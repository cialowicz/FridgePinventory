# Module for system diagnostics

import logging
from typing import Tuple

from .audio_feedback_manager import AudioFeedbackManager
from .display_manager import display_text, initialize_display, is_display_supported
from .motion_sensor_manager import MotionSensorManager


def run_startup_diagnostics(
    config_manager,
    motion_manager=None,
    audio_manager=None,
) -> Tuple[bool, bool, bool, object]:
    """Run startup diagnostics.

    Returns: (display_ok, motion_sensor_ok, audio_ok, display_instance)
    """
    display_ok = False
    motion_sensor_ok = False
    audio_ok = False
    display = None
    display_initialized = False

    if is_display_supported(config_manager):
        display = initialize_display(config_manager)
        if display:
            display_initialized = True
            logging.info("Display initialized successfully")
            show_startup = config_manager.get(
                'display',
                'show_startup_message',
                default=False,
            )
            if show_startup is True:
                display_text(
                    display,
                    "FridgePinventory\nstarting up...",
                    config_manager=config_manager,
                )
        else:
            logging.error("Failed to initialize display")
    else:
        logging.warning("Display not supported on this platform")

    owns_motion_manager = motion_manager is None
    if motion_manager is None:
        motion_manager = MotionSensorManager(config_manager=config_manager)
    if motion_manager.is_supported():
        try:
            readings = [motion_manager.detect_motion() for _ in range(3)]
            if motion_manager.is_healthy():
                motion_sensor_ok = True
                logging.info("Motion sensor initialized successfully")
                logging.info(f"Initial motion sensor readings: {readings}")
            else:
                logging.error(f"Motion sensor failed diagnostics: {motion_manager.last_error}")
        except Exception as e:
            logging.error(f"Motion sensor error: {e}")
        finally:
            if owns_motion_manager:
                motion_manager.cleanup()
    else:
        logging.warning("Motion sensor not supported on this platform")

    owns_audio_manager = audio_manager is None
    if audio_manager is None:
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
        if owns_audio_manager:
            audio_manager.cleanup()

    if display_initialized and display:
        status_text = (
            "Diagnostics complete:\n"
            "Display: OK\n"
            f"Motion: {'OK' if motion_sensor_ok else 'FAIL'}\n"
            f"Audio: {'OK' if audio_ok else 'FAIL'}"
        )
        if display_text(display, status_text, config_manager=config_manager):
            display_ok = True
        else:
            logging.error("Failed to render diagnostics status")

    return display_ok, motion_sensor_ok, audio_ok, display
