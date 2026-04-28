# Motion sensor manager with proper encapsulation and no global state

import logging
import subprocess
import threading
from typing import Optional

from . import platform_info


class MotionSensorManager:
    """Manages motion sensor with proper encapsulation and thread safety."""
    
    def __init__(self, pin: Optional[int] = None, config_manager=None):
        """Initialize motion sensor manager.
        
        Args:
            pin: GPIO pin number. If None, uses config or default.
            config_manager: Configuration manager instance.
        """
        self._config = config_manager
        self._lock = threading.Lock()
        self._initialized = False
        self._gpio = None
        self._gpiozero_sensor = None
        self._last_error: Optional[str] = None
        self._pin = pin or self._get_configured_pin()
        self._is_pi5 = platform_info.is_raspberry_pi_5()
        self._is_pi = platform_info.is_raspberry_pi()
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
            if self._config is None:
                return {}
            hw = self._config.get_hardware_config()
        except Exception:
            hw = {}
        if not isinstance(hw, dict):
            hw = {}
        motion = hw.get('motion_sensor', {})
        if not isinstance(motion, dict):
            motion = {}
        return motion
    
    def _init_gpio_module(self):
        """Initialize GPIO module for non-Pi5 systems."""
        try:
            import RPi.GPIO as GPIO
            self._gpio = GPIO
        except ImportError:
            self.logger.warning("RPi.GPIO not available, using mock")
            self._gpio = platform_info.MockGPIO()
    
    def is_supported(self) -> bool:
        """Check if motion sensor functionality is available and enabled."""
        cfg = self._get_motion_config()
        enabled = cfg.get('enabled', True)
        return enabled and self._is_pi

    @property
    def last_error(self) -> Optional[str]:
        """Most recent hardware error, if any."""
        return self._last_error

    def is_healthy(self) -> bool:
        """Return whether the last hardware interaction completed without error."""
        return self._last_error is None

    def _set_error(self, message: str) -> None:
        self._last_error = message
        self.logger.error(message)

    def _clear_error(self) -> None:
        self._last_error = None

    def _setup_gpiozero_pi5(self) -> bool:
        """Use gpiozero/lgpio on Pi 5 when installed to avoid shelling out per read."""
        if self._gpiozero_sensor is not None:
            return True

        try:
            from gpiozero import MotionSensor
            self._gpiozero_sensor = MotionSensor(self._pin, pull_up=False)
            self.logger.info(f"Initialized gpiozero motion sensor on pin {self._pin}")
            self._clear_error()
            return True
        except ImportError:
            self.logger.debug("gpiozero not available for Pi 5 motion reads; falling back to pinctrl")
            return False
        except Exception as e:
            self._gpiozero_sensor = None
            self._set_error(f"Failed to initialize gpiozero motion sensor: {e}")
            return False
    
    def _setup_pin_pi5(self) -> bool:
        """Setup GPIO pin on Raspberry Pi 5."""
        if not isinstance(self._pin, int) or self._pin < 0 or self._pin > 27:
            self._set_error(f"Invalid GPIO pin number: {self._pin}")
            return False

        cfg = self._get_motion_config()
        if cfg.get('read_method') != 'pinctrl' and self._setup_gpiozero_pi5():
            return True
        
        cmd = ['pinctrl', 'set', str(self._pin), 'ip', 'pd']
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=5)
            self._clear_error()
            return True
        except (subprocess.CalledProcessError, PermissionError) as e:
            if cfg.get('allow_sudo', False):
                self.logger.warning("pinctrl setup requires elevated permissions, using sudo")
                cmd = ['sudo'] + cmd
                try:
                    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=5)
                    self._clear_error()
                    return True
                except Exception as e:
                    self._set_error(f"Failed to setup pin with sudo: {e}")
                    return False
            else:
                self._set_error(
                    "Permission denied for pinctrl. Configure udev rules or set allow_sudo in config"
                )
                return False
        except Exception as e:
            self._set_error(f"Failed to setup pin with pinctrl: {e}")
            return False
    
    def _read_pin_pi5(self) -> bool:
        """Read GPIO pin state on Raspberry Pi 5."""
        if not isinstance(self._pin, int) or self._pin < 0 or self._pin > 27:
            self._set_error(f"Invalid GPIO pin number: {self._pin}")
            return False

        if self._gpiozero_sensor is not None:
            try:
                motion_detected = bool(self._gpiozero_sensor.motion_detected)
                self._clear_error()
                return motion_detected
            except Exception as e:
                self._set_error(f"Failed to read gpiozero motion sensor: {e}")
                return False
        
        cmd = ['pinctrl', 'get', str(self._pin)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
            self._clear_error()
            return 'level=1' in result.stdout
        except (subprocess.CalledProcessError, PermissionError) as e:
            cfg = self._get_motion_config()
            if cfg.get('allow_sudo', False):
                cmd = ['sudo'] + cmd
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
                    self._clear_error()
                    return 'level=1' in result.stdout
                except Exception as sudo_error:
                    self._set_error(f"Failed to read pin with sudo: {sudo_error}")
                    return False
            self._set_error(f"Failed to read pin with pinctrl: {e}")
            return False
        except Exception as e:
            self._set_error(f"Unexpected error reading pin with pinctrl: {e}")
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
                                self._set_error(f"Failed to initialize GPIO: {e}")
                                return False
                        else:
                            return False
                
                if self._gpio:
                    motion_detected = bool(self._gpio.input(self._pin))
                    self._clear_error()
                    if motion_detected:
                        self.logger.info(f"Motion detected on pin {self._pin}")
                    return motion_detected
                return False
        
        except Exception as e:
            self._set_error(f"Error detecting motion: {e}")
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
                    self._set_error(f"Error during GPIO cleanup: {e}")
            if self._gpiozero_sensor is not None:
                try:
                    self._gpiozero_sensor.close()
                    self._gpiozero_sensor = None
                    self._initialized = False
                    self.logger.info("gpiozero motion sensor cleanup completed")
                except Exception as e:
                    self._set_error(f"Error during gpiozero cleanup: {e}")
