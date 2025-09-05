# Motion sensor manager with proper encapsulation and no global state

import os
import logging
import subprocess
import threading
from typing import Optional
from .config_manager import config

class MotionSensorManager:
    """Manages motion sensor with proper encapsulation and thread safety."""
    
    def __init__(self, pin: Optional[int] = None, config_manager=None):
        """Initialize motion sensor manager.
        
        Args:
            pin: GPIO pin number. If None, uses config or default.
            config_manager: Configuration manager instance.
        """
        self._config = config_manager or config
        self._lock = threading.Lock()
        self._initialized = False
        self._gpio = None
        self._pin = pin or self._get_configured_pin()
        self._is_pi5 = self._check_raspberry_pi_5()
        self._is_pi = self._check_raspberry_pi()
        self.logger = logging.getLogger(__name__)
        
        # Initialize GPIO if on Raspberry Pi
        if self._is_pi and not self._is_pi5:
            self._init_gpio_module()
    
    def _get_configured_pin(self) -> int:
        """Get configured pin from config."""
        cfg = self._get_motion_config()
        return cfg.get('pin', 4)  # Default to pin 4
    
    def _get_motion_config(self):
        """Safely retrieve motion sensor config as a plain dict."""
        try:
            hw = self._config.get_hardware_config()
        except Exception:
            hw = {}
        if not isinstance(hw, dict):
            hw = {}
        motion = hw.get('motion_sensor', {})
        if not isinstance(motion, dict):
            motion = {}
        return motion
    
    def _check_raspberry_pi(self) -> bool:
        """Check if we're running on a Raspberry Pi."""
        if os.path.exists('/proc/device-tree/model'):
            try:
                with open('/proc/device-tree/model', 'r') as f:
                    model = f.read().lower()
                    return 'raspberry pi' in model
            except Exception:
                pass
        return False
    
    def _check_raspberry_pi_5(self) -> bool:
        """Check if we're running on a Raspberry Pi 5."""
        if os.path.exists('/proc/device-tree/model'):
            try:
                with open('/proc/device-tree/model', 'r') as f:
                    model = f.read().lower()
                    return 'raspberry pi 5' in model
            except Exception:
                pass
        return False
    
    def _init_gpio_module(self):
        """Initialize GPIO module for non-Pi5 systems."""
        try:
            import RPi.GPIO as GPIO
            self._gpio = GPIO
        except ImportError:
            self.logger.warning("RPi.GPIO not available, using mock")
            self._gpio = self._create_mock_gpio()
    
    def _create_mock_gpio(self):
        """Create a mock GPIO for testing."""
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
        
        return MockGPIO()
    
    def is_supported(self) -> bool:
        """Check if motion sensor functionality is available and enabled."""
        cfg = self._get_motion_config()
        enabled = cfg.get('enabled', True)
        return enabled and self._is_pi
    
    def _setup_pin_pi5(self) -> bool:
        """Setup GPIO pin on Raspberry Pi 5."""
        if not isinstance(self._pin, int) or self._pin < 0 or self._pin > 27:
            self.logger.error(f"Invalid GPIO pin number: {self._pin}")
            return False
        
        cmd = ['pinctrl', 'set', str(self._pin), 'ip', 'pd']
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=5)
            return True
        except (subprocess.CalledProcessError, PermissionError):
            cfg = self._get_motion_config()
            if cfg.get('allow_sudo', False):
                self.logger.warning("pinctrl setup requires elevated permissions, using sudo")
                cmd = ['sudo'] + cmd
                try:
                    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=5)
                    return True
                except Exception as e:
                    self.logger.error(f"Failed to setup pin with sudo: {e}")
                    return False
            else:
                self.logger.error("Permission denied for pinctrl. Configure udev rules or set allow_sudo in config")
                return False
    
    def _read_pin_pi5(self) -> bool:
        """Read GPIO pin state on Raspberry Pi 5."""
        if not isinstance(self._pin, int) or self._pin < 0 or self._pin > 27:
            return False
        
        cmd = ['pinctrl', 'get', str(self._pin)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
            return 'level=1' in result.stdout
        except (subprocess.CalledProcessError, PermissionError):
            cfg = self._get_motion_config()
            if cfg.get('allow_sudo', False):
                cmd = ['sudo'] + cmd
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
                    return 'level=1' in result.stdout
                except Exception:
                    return False
            return False
        except Exception:
            return False
    
    def detect_motion(self) -> bool:
        """Detect motion using the PIR sensor."""
        if not self.is_supported():
            self.logger.debug("Motion sensor not supported or disabled")
            return False
        
        try:
            if self._is_pi5:
                # Pi 5 uses pinctrl
                with self._lock:
                    if not self._initialized:
                        if not self._setup_pin_pi5():
                            return False
                        self._initialized = True
                
                motion_detected = self._read_pin_pi5()
                if motion_detected:
                    self.logger.info(f"Motion detected on pin {self._pin}")
                return motion_detected
            else:
                # Older Pi uses RPi.GPIO
                with self._lock:
                    if not self._initialized:
                        if self._gpio:
                            try:
                                self._gpio.setmode(self._gpio.BCM)
                                self._gpio.setup(self._pin, self._gpio.IN)
                                self._initialized = True
                            except Exception as e:
                                self.logger.error(f"Failed to initialize GPIO: {e}")
                                return False
                        else:
                            return False
                
                if self._gpio:
                    motion_detected = bool(self._gpio.input(self._pin))
                    if motion_detected:
                        self.logger.info(f"Motion detected on pin {self._pin}")
                    return motion_detected
                return False
        
        except Exception as e:
            self.logger.error(f"Error detecting motion: {e}")
            return False
    
    def cleanup(self):
        """Clean up GPIO resources."""
        with self._lock:
            if self._initialized and not self._is_pi5 and self._gpio:
                try:
                    self._gpio.cleanup()
                    self._initialized = False
                    self.logger.info("GPIO cleanup completed")
                except Exception as e:
                    self.logger.error(f"Error during GPIO cleanup: {e}")

# Create a default instance for backward compatibility
_default_manager = None

def get_default_motion_sensor_manager():
    """Get the default motion sensor manager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = MotionSensorManager()
    return _default_manager

# Backward compatibility functions
def detect_motion() -> bool:
    """Detect motion using the default manager."""
    return get_default_motion_sensor_manager().detect_motion()

def cleanup():
    """Clean up the default manager."""
    get_default_motion_sensor_manager().cleanup()

def is_motion_sensor_supported() -> bool:
    """Check if motion sensor is supported."""
    return get_default_motion_sensor_manager().is_supported()
