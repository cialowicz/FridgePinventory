# Module for motion sensor functionality

import os
import logging
import time
import subprocess
from typing import Optional

# GPIO pin for motion sensor
MOTION_SENSOR_PIN = 4

# Global variable to track GPIO initialization
_gpio_initialized = False

def _is_raspberry_pi():
    """Check if we're running on a Raspberry Pi."""
    # Check for Raspberry Pi specific files
    if os.path.exists('/proc/device-tree/model'):
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().lower()
            return 'raspberry pi' in model
    return False

def _is_raspberry_pi_5():
    """Check if we're running on a Raspberry Pi 5."""
    if os.path.exists('/proc/device-tree/model'):
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().lower()
            return 'raspberry pi 5' in model
    return False

# Mock GPIO for testing
class MockGPIO:
    BCM = 'BCM'
    IN = 'IN'
    OUT = 'OUT'
    
    @staticmethod
    def setmode(mode):
        pass
    
    @staticmethod
    def setup(pin, mode):
        pass
    
    @staticmethod
    def input(pin):
        return False
    
    @staticmethod
    def cleanup():
        pass

# Initialize GPIO or mock
GPIO = None
try:
    if _is_raspberry_pi():
        if _is_raspberry_pi_5():
            # For Pi 5, we'll use pinctrl directly
            GPIO = None
        else:
            # For older Pis, use RPi.GPIO
            import RPi.GPIO as GPIO
    else:
        GPIO = MockGPIO()
except ImportError:
    logging.error("Failed to import RPi.GPIO. Using mock GPIO.")
    GPIO = MockGPIO()

def is_motion_sensor_supported() -> bool:
    """Check if motion sensor functionality is available."""
    return _is_raspberry_pi()

def _read_pinctrl(pin: int) -> bool:
    """Read GPIO pin state using pinctrl."""
    try:
        result = subprocess.run(['pinctrl', 'get', str(pin)], 
                              capture_output=True, text=True, check=True)
        return 'level=1' in result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"Error reading pinctrl: {e}")
        return False
    except FileNotFoundError:
        logging.error("pinctrl command not found")
        return False

def detect_motion() -> bool:
    """Detect motion using the PIR sensor."""
    global _gpio_initialized
    
    if not is_motion_sensor_supported():
        return False
        
    try:
        if _is_raspberry_pi_5():
            # Use pinctrl for Pi 5
            return _read_pinctrl(MOTION_SENSOR_PIN)
        else:
            # Use RPi.GPIO for older Pis
            if not _gpio_initialized:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(MOTION_SENSOR_PIN, GPIO.IN)
                _gpio_initialized = True
            return bool(GPIO.input(MOTION_SENSOR_PIN))
        
    except Exception as e:
        logging.error(f"Error detecting motion: {e}")
        return False

def cleanup():
    """Clean up GPIO resources."""
    global _gpio_initialized
    
    if _gpio_initialized and not _is_raspberry_pi_5():
        try:
            GPIO.cleanup()
            _gpio_initialized = False
        except Exception as e:
            logging.error(f"Error cleaning up GPIO: {e}")
