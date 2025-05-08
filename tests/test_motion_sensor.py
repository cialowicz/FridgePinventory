# Tests for motion sensor module

import pytest
from unittest.mock import patch, MagicMock
from pi_inventory_system.motion_sensor import (
    detect_motion,
    is_motion_sensor_supported,
    MOTION_SENSOR_PIN
)

def test_motion_detected(mock_gpio_environment):
    """Test when motion is detected."""
    _, mock_gpio = mock_gpio_environment
    mock_gpio.input.return_value = 1
    assert detect_motion()
    mock_gpio.input.assert_called_once_with(MOTION_SENSOR_PIN)

def test_no_motion_detected(mock_gpio_environment):
    """Test when no motion is detected."""
    _, mock_gpio = mock_gpio_environment
    mock_gpio.input.return_value = 0
    assert not detect_motion()
    mock_gpio.input.assert_called_once_with(MOTION_SENSOR_PIN)

def test_gpio_error_handling(mock_gpio_environment):
    """Test error handling when GPIO fails."""
    _, mock_gpio = mock_gpio_environment
    mock_gpio.input.side_effect = Exception("GPIO error")
    assert not detect_motion()
    mock_gpio.input.assert_called_once_with(MOTION_SENSOR_PIN)

def test_motion_sensor_supported_with_gpio(mock_gpio_environment):
    """Test motion sensor support detection with GPIO available."""
    assert is_motion_sensor_supported()

def test_motion_sensor_not_supported_without_gpio(mock_gpio_environment):
    """Test motion sensor support detection without GPIO."""
    mock_is_pi, _ = mock_gpio_environment
    mock_is_pi.return_value = False  # Simulate not running on a Pi
    assert not is_motion_sensor_supported()

def test_motion_sensor_initialization(mock_gpio_environment):
    """Test motion sensor initialization."""
    _, mock_gpio = mock_gpio_environment
    # Reset GPIO mock to clear any previous calls
    mock_gpio.reset_mock()
    
    # Call detect_motion to trigger initialization
    detect_motion()
    
    # Verify GPIO initialization
    mock_gpio.setmode.assert_called_once_with(mock_gpio.BCM)
    mock_gpio.setup.assert_called_once_with(MOTION_SENSOR_PIN, mock_gpio.IN)

@pytest.mark.skip(reason="Hardware-dependent test")
def test_real_motion_detection():
    """Test actual motion detection with real hardware."""
    # This test requires actual hardware and should be skipped in CI
    result = detect_motion()
    assert isinstance(result, bool)
