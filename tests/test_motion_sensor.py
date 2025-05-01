# Tests for motion sensor module

import unittest
from unittest.mock import patch, MagicMock
from src.pi_inventory_system.motion_sensor import (
    detect_motion,
    is_motion_sensor_supported,
    MOTION_SENSOR_PIN
)


class TestMotionSensor(unittest.TestCase):
    """Test cases for motion sensor functionality."""

    def setUp(self):
        """Set up test environment."""
        # Reset the _gpio_initialized state
        import src.pi_inventory_system.motion_sensor as motion_sensor
        motion_sensor._gpio_initialized = False

        self.platform_patcher = patch('src.pi_inventory_system.motion_sensor.platform')
        self.mock_platform = self.platform_patcher.start()
        self.mock_platform.system.return_value = 'Linux'
        self.mock_platform.machine.return_value = 'armv7l'

        self.gpio_patcher = patch('src.pi_inventory_system.motion_sensor.GPIO')
        self.mock_gpio = self.gpio_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        self.platform_patcher.stop()
        self.gpio_patcher.stop()

    def test_motion_detected(self):
        """Test when motion is detected."""
        self.mock_gpio.input.return_value = 1
        self.assertTrue(detect_motion())
        self.mock_gpio.input.assert_called_once_with(MOTION_SENSOR_PIN)

    def test_no_motion_detected(self):
        """Test when no motion is detected."""
        self.mock_gpio.input.return_value = 0
        self.assertFalse(detect_motion())
        self.mock_gpio.input.assert_called_once_with(MOTION_SENSOR_PIN)

    def test_gpio_error_handling(self):
        """Test error handling when GPIO fails."""
        self.mock_gpio.input.side_effect = Exception("GPIO error")
        self.assertFalse(detect_motion())
        self.mock_gpio.input.assert_called_once_with(MOTION_SENSOR_PIN)

    def test_motion_sensor_supported_with_gpio(self):
        """Test motion sensor support detection with GPIO available."""
        self.assertTrue(is_motion_sensor_supported())

    def test_motion_sensor_not_supported_without_gpio(self):
        """Test motion sensor support detection without GPIO."""
        self.mock_platform.system.return_value = 'Darwin'
        self.assertFalse(is_motion_sensor_supported())

    def test_motion_sensor_initialization(self):
        """Test motion sensor initialization."""
        # Reset GPIO mock to clear any previous calls
        self.mock_gpio.reset_mock()
        
        # Call detect_motion to trigger initialization
        detect_motion()
        
        # Verify GPIO initialization
        self.mock_gpio.setmode.assert_called_once_with(self.mock_gpio.BCM)
        self.mock_gpio.setup.assert_called_once_with(MOTION_SENSOR_PIN, self.mock_gpio.IN)

    @unittest.skip("Hardware-dependent test")
    def test_real_motion_detection(self):
        """Test actual motion detection with real hardware."""
        # This test requires actual hardware and should be skipped in CI
        result = detect_motion()
        self.assertIsInstance(result, bool)


if __name__ == '__main__':
    unittest.main()
