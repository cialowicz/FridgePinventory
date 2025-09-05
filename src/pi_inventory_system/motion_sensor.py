# Module for motion sensor functionality

import os
import logging
import time
import subprocess
import threading
import shlex
from typing import Optional
from .config_manager import config

# GPIO pin for motion sensor
MOTION_SENSOR_PIN = 4

# Thread-safe initialization tracking
_gpio_initialized = False
_gpio_lock = threading.Lock()

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
        # Validate pin number
        if not isinstance(pin, int) or pin < 0 or pin > 27:
            logging.error(f"Invalid GPIO pin number: {pin}")
            return False
        
        # Try to read without sudo first (may work if permissions are set)
        cmd = ['pinctrl', 'get', str(pin)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  check=True, timeout=5)
            logging.debug(f"pinctrl output for pin {pin}: {result.stdout.strip()}")
            return 'level=1' in result.stdout
        except (subprocess.CalledProcessError, PermissionError):
            # If permission denied, check if we should use sudo
            cfg = _get_motion_config()
            if cfg.get('allow_sudo', False):
                logging.warning("pinctrl requires elevated permissions, using sudo (configure udev rules to avoid this)")
                cmd = ['sudo', 'pinctrl', 'get', str(pin)]
                result = subprocess.run(cmd, capture_output=True, text=True, 
                                      check=True, timeout=5)
                logging.debug(f"pinctrl output for pin {pin}: {result.stdout.strip()}")
                return 'level=1' in result.stdout
            else:
                logging.error(f"Permission denied for pinctrl. Configure udev rules or set allow_sudo in config")
                return False
    except subprocess.TimeoutExpired:
        logging.error(f"Timeout reading pinctrl for pin {pin}")
        return False
    except subprocess.CalledProcessError as e:
        logging.error(f"Error reading pinctrl: {e}")
        logging.error(f"Error output: {e.stderr}")
        return False
    except FileNotFoundError:
        logging.error("pinctrl command not found")
        return False
    except Exception as e:
        logging.error(f"Unexpected error reading pinctrl: {e}")
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
            # Thread-safe initialization
            with _gpio_lock:
                if not _gpio_initialized:
                    try:
                        logging.info(f"Configuring GPIO {pin} for Pi 5 as input with pull-down.")
                        # Validate pin number
                        if not isinstance(pin, int) or pin < 0 or pin > 27:
                            logging.error(f"Invalid GPIO pin number: {pin}")
                            return False
                        
                        # Try without sudo first
                        cmd = ['pinctrl', 'set', str(pin), 'ip', 'pd']
                        try:
                            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=5)
                            _gpio_initialized = True
                        except (subprocess.CalledProcessError, PermissionError) as e:
                            cfg = _get_motion_config()
                            if cfg.get('allow_sudo', False):
                                logging.warning("pinctrl setup requires elevated permissions, using sudo")
                                cmd = ['sudo', 'pinctrl', 'set', str(pin), 'ip', 'pd']
                                subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=5)
                                _gpio_initialized = True
                            else:
                                logging.error(f"Permission denied for pinctrl setup. Configure udev rules or set allow_sudo in config")
                                return False
                    except subprocess.CalledProcessError as e:
                        logging.error(f"Failed to configure GPIO pin {pin} using pinctrl: {e}")
                        logging.error(f"Error output: {e.stderr}")
                        return False
                    except Exception as e:
                        logging.error(f"Unexpected error configuring GPIO pin {pin}: {e}")
                        return False

            motion_detected = _read_pinctrl(pin)
            if motion_detected:
                logging.info(f"Motion detected via pinctrl on pin {pin}")
            return motion_detected
        else:
            # Thread-safe initialization for RPi.GPIO
            with _gpio_lock:
                if not _gpio_initialized:
                    try:
                        GPIO.setmode(GPIO.BCM)
                        GPIO.setup(pin, GPIO.IN)
                        _gpio_initialized = True
                        logging.debug(f"GPIO initialized for pin {pin}")
                    except Exception as e:
                        logging.error(f"Failed to initialize GPIO: {e}")
                        return False
            
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
    
    with _gpio_lock:
        if _gpio_initialized and not _is_raspberry_pi_5():
            try:
                GPIO.cleanup()
                _gpio_initialized = False
                logging.info("GPIO cleanup completed successfully")
            except Exception as e:
                logging.error(f"Error cleaning up GPIO: {e}")
