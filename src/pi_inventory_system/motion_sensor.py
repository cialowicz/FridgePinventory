# Module for motion sensor functionality

import platform
import logging
from typing import Optional

# GPIO pin for motion sensor
MOTION_SENSOR_PIN = 4

# Global variable to track GPIO initialization
_gpio_initialized = False

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
    if platform.system() == 'Linux' and platform.machine().startswith('arm'):
        import RPi.GPIO as GPIO
    else:
        GPIO = MockGPIO()
except ImportError:
    GPIO = MockGPIO()

def is_motion_sensor_supported() -> bool:
    """Check if motion sensor functionality is available."""
    return platform.system() == 'Linux' and platform.machine().startswith('arm')

def detect_motion() -> bool:
    """Detect motion using the PIR sensor."""
    global _gpio_initialized
    
    if not is_motion_sensor_supported():
        return False
        
    try:
        # Initialize GPIO if not already done
        if not _gpio_initialized:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(MOTION_SENSOR_PIN, GPIO.IN)
            _gpio_initialized = True
            
        # Read the sensor
        return bool(GPIO.input(MOTION_SENSOR_PIN))
        
    except Exception as e:
        logging.error(f"Error detecting motion: {e}")
        return False

def cleanup():
    """Clean up GPIO resources."""
    global _gpio_initialized
    
    if _gpio_initialized:
        try:
            GPIO.cleanup()
            _gpio_initialized = False
        except Exception as e:
            logging.error(f"Error cleaning up GPIO: {e}")
