# Tests for motion sensor module

import pytest
from unittest.mock import patch, MagicMock
import platform
from pi_inventory_system.motion_sensor import (
    detect_motion,
    is_motion_sensor_supported,
    _gpio_initialized
)

@pytest.fixture
def mock_gpio():
    """Fixture to mock GPIO module."""
    with patch('pi_inventory_system.motion_sensor.GPIO') as mock:
        mock.BCM = 'BCM'
        mock.IN = 'IN'
        mock.input.return_value = False
        yield mock

@pytest.fixture
def mock_platform():
    """Fixture to mock platform information."""
    with patch('pi_inventory_system.motion_sensor.platform') as mock:
        mock.system.return_value = 'Linux'
        mock.machine.return_value = 'armv7l'
        yield mock

def test_is_motion_sensor_supported_raspberry_pi(mock_platform):
    """Test motion sensor support detection on Raspberry Pi."""
    assert is_motion_sensor_supported() is True

def test_is_motion_sensor_supported_non_raspberry_pi(mock_platform):
    """Test motion sensor support detection on non-Raspberry Pi."""
    mock_platform.system.return_value = 'Darwin'
    assert is_motion_sensor_supported() is False

def test_detect_motion_raspberry_pi(mock_gpio, mock_platform):
    """Test motion detection on Raspberry Pi."""
    mock_platform['system'].return_value = 'Linux'
    mock_platform['machine'].return_value = 'armv7l'
    
    # Test motion detected
    mock_gpio.input.return_value = True
    assert detect_motion() is True
    
    # Test no motion detected
    mock_gpio.input.return_value = False
    assert detect_motion() is False
    
    # Verify GPIO was initialized
    mock_gpio.setmode.assert_called_once_with(mock_gpio.BCM)
    mock_gpio.setup.assert_called_once_with(4, mock_gpio.IN)

def test_detect_motion_non_raspberry_pi(mock_platform):
    """Test motion detection on non-Raspberry Pi."""
    mock_platform.system.return_value = 'Darwin'
    assert detect_motion() is False

def test_detect_motion_error_handling(mock_gpio, mock_platform):
    """Test error handling in motion detection."""
    mock_platform.system.return_value = 'Linux'
    mock_platform.machine.return_value = 'armv7l'
    
    # Simulate GPIO error
    mock_gpio.input.side_effect = Exception("GPIO error")
    assert detect_motion() is False

def test_gpio_initialization_once(mock_gpio, mock_platform):
    """Test that GPIO is only initialized once."""
    # Reset the initialization state
    import pi_inventory_system.motion_sensor
    pi_inventory_system.motion_sensor._gpio_initialized = False
    
    # Call detect_motion multiple times
    pi_inventory_system.motion_sensor.detect_motion()
    pi_inventory_system.motion_sensor.detect_motion()
    pi_inventory_system.motion_sensor.detect_motion()
    
    # Verify GPIO was initialized only once
    mock_gpio.setmode.assert_called_once_with(mock_gpio.BCM)
    mock_gpio.setup.assert_called_once_with(4, mock_gpio.IN)

@pytest.mark.skipif(not platform.system() == 'Linux' or not platform.machine().startswith('arm'),
                   reason="Test requires actual Raspberry Pi hardware")
def test_detect_motion_hardware():
    """Test motion detection on actual Raspberry Pi hardware."""
    result = detect_motion()
    assert isinstance(result, bool)
