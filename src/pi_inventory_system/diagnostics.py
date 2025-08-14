# Module for system diagnostics

import time
import logging
from typing import Tuple
from pi_inventory_system.display_manager import initialize_display, display_text, is_display_supported
from pi_inventory_system.motion_sensor import detect_motion, is_motion_sensor_supported
from pi_inventory_system.audio_feedback import play_feedback_sound
from pi_inventory_system.voice_recognition import recognize_speech_from_mic
import pyttsx3

def run_startup_diagnostics() -> Tuple[bool, bool, bool]:
    """
    Run startup diagnostics and return status of display, motion sensor, and audio.
    Returns: (display_ok, motion_sensor_ok, audio_ok)
    """
    display_ok = False
    motion_sensor_ok = False
    audio_ok = False
    
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
    
    # Check audio
    try:
        # Play success sound
        if play_feedback_sound(True):
            logging.info("Success sound played successfully")
            
            # Initialize text-to-speech
            engine = pyttsx3.init()
            engine.say("Fridge Pinventory is starting up. Please say 'test' to confirm microphone is working.")
            engine.runAndWait()
            
            # Wait for microphone input
            logging.info("Waiting for microphone test...")
            command = recognize_speech_from_mic()
            if command and "test" in command.lower():
                audio_ok = True
                logging.info("Microphone test successful")
                play_feedback_sound(True)
            else:
                logging.error("Microphone test failed")
                play_feedback_sound(False)
        else:
            logging.error("Failed to play success sound")
            play_feedback_sound(False)
    except Exception as e:
        logging.error(f"Audio diagnostics error: {e}")
        play_feedback_sound(False)
    
    # Final status display
    if display_ok:
        status_text = "Diagnostics complete:\n"
        status_text += f"Display: {'OK' if display_ok else 'FAIL'}\n"
        status_text += f"Motion: {'OK' if motion_sensor_ok else 'FAIL'}\n"
        status_text += f"Audio: {'OK' if audio_ok else 'FAIL'}"
        display_text(display, status_text)
    
    return display_ok, motion_sensor_ok, audio_ok
