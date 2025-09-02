# Module for motion sensor functionality

import os
import logging
import time
import subprocess
from typing import Optional
from .config_manager import config

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

def _get_motion_config():
    """Safely retrieve motion sensor config as a plain dict."""
    try:
        hw = config.get_hardware_config()
    except Exception:
        hw = {}
    # Ensure we have a dict (tests may patch config with MagicMock)
    if not isinstance(hw, dict):
        hw = {}
    motion = hw.get('motion_sensor', {})
    if not isinstance(motion, dict):
        motion = {}
    return motion

def is_motion_sensor_supported() -> bool:
    """Check if motion sensor functionality is available and enabled by config."""
    cfg = _get_motion_config()
    enabled = cfg.get('enabled', True)
    return enabled and _is_raspberry_pi()

def _read_pinctrl(pin: int) -> bool:
    """Read GPIO pin state using pinctrl."""
    try:
        # Note: sudo is required for pinctrl on Pi 5
        result = subprocess.run(['sudo', 'pinctrl', 'get', str(pin)], 
                              capture_output=True, text=True, check=True)
        logging.debug(f"pinctrl output for pin {pin}: {result.stdout.strip()}")
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
        logging.debug("Motion sensor not supported or disabled")
        return False
        
    try:
        # Use configured pin if provided, else default constant
        cfg = _get_motion_config()
        pin = cfg.get('pin') if cfg.get('pin') is not None else MOTION_SENSOR_PIN
        
        logging.debug(f"Checking motion on pin {pin}, Pi 5: {_is_raspberry_pi_5()}")

        if _is_raspberry_pi_5():
            # On Pi 5, we use pinctrl and must initialize the pin once.
            if not _gpio_initialized:
                try:
                    logging.info(f"Configuring GPIO {pin} for Pi 5 as input with pull-down.")
                    subprocess.run(['sudo', 'pinctrl', 'set', str(pin), 'ip', 'pd'], check=True)
                    _gpio_initialized = True
                except Exception as e:
                    logging.error(f"Failed to configure GPIO pin {pin} using pinctrl: {e}")
                    return False # Can't proceed if pin setup fails

            motion_detected = _read_pinctrl(pin)
            if motion_detected:
                logging.info(f"Motion detected via pinctrl on pin {pin}")
            return motion_detected
        else:
            # Use RPi.GPIO for older Pis
            if not _gpio_initialized:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(pin, GPIO.IN)
                _gpio_initialized = True
                logging.debug(f"GPIO initialized for pin {pin}")
            
            motion_detected = bool(GPIO.input(pin))
            if motion_detected:
                logging.info(f"Motion detected via GPIO on pin {pin}")
            return motion_detected
        
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
