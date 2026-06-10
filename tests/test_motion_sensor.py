# Tests for motion sensor manager

import pytest
from unittest.mock import patch, MagicMock
import sys
from pi_inventory_system.motion_sensor_manager import MotionSensorManager

@pytest.fixture
def mock_config_manager():
    """Provides a mock config manager for tests."""
    config = MagicMock()
    config.get_hardware_config.return_value = {
        'motion_sensor': {'pin': 4, 'enabled': True}
    }
    return config

@patch('pi_inventory_system.platform_info.is_raspberry_pi_5', return_value=False)
@patch('pi_inventory_system.platform_info.is_raspberry_pi', return_value=True)
def test_detect_motion_on_pi(mock_check_pi, mock_check_pi5, mock_config_manager):
    """Test motion detection on a non-Pi5 Raspberry Pi."""
    # Create mock GPIO module that will be returned by the import
    mock_gpio = MagicMock()
    mock_gpio.BCM = 'BCM'
    mock_gpio.IN = 'IN'
    
    # Patch the _init_gpio_module method to set our mock directly
    def mock_init_gpio(self):
        self._gpio = mock_gpio
    
    with patch.object(MotionSensorManager, '_init_gpio_module', mock_init_gpio):
        manager = MotionSensorManager(config_manager=mock_config_manager)
        
        # Test motion detected
        mock_gpio.input.return_value = True
        assert manager.detect_motion() is True
        mock_gpio.setmode.assert_called_once_with('BCM')
        mock_gpio.setup.assert_called_once_with(4, 'IN')
        mock_gpio.input.assert_called_once_with(4)

        # Test no motion
        mock_gpio.reset_mock()
        mock_gpio.input.return_value = False
        assert manager.detect_motion() is False
        # Initialization should not happen again
        mock_gpio.setmode.assert_not_called()
        mock_gpio.setup.assert_not_called()
        assert mock_gpio.input.call_count == 1

@patch('pi_inventory_system.platform_info.is_raspberry_pi', return_value=False)
def test_motion_sensor_unsupported_on_non_pi(mock_check_pi, mock_config_manager):
    """Test that motion sensor is not supported on non-Pi systems."""
    manager = MotionSensorManager(config_manager=mock_config_manager)
    assert manager.is_supported() is False
    assert manager.is_available() is False
    assert manager.detect_motion() is False


@patch('pi_inventory_system.platform_info.is_raspberry_pi_5', return_value=False)
@patch('pi_inventory_system.platform_info.is_raspberry_pi', return_value=True)
def test_motion_sensor_available_after_initialization(
    mock_check_pi,
    mock_check_pi5,
    mock_config_manager,
):
    mock_gpio = MagicMock()
    mock_gpio.BCM = 'BCM'
    mock_gpio.IN = 'IN'

    def mock_init_gpio(self):
        self._gpio = mock_gpio

    with patch.object(MotionSensorManager, '_init_gpio_module', mock_init_gpio):
        manager = MotionSensorManager(config_manager=mock_config_manager)
        assert manager.is_available() is True
        mock_gpio.setup.assert_called_once_with(4, 'IN')

@patch('pi_inventory_system.platform_info.is_raspberry_pi_5', return_value=True)
@patch('pi_inventory_system.platform_info.is_raspberry_pi', return_value=True)
@patch('pi_inventory_system.motion_sensor_manager.subprocess.run')
def test_detect_motion_on_pi5(mock_subprocess, mock_check_pi, mock_check_pi5, mock_config_manager):
    """Test motion detection on Raspberry Pi 5 using pinctrl."""
    with patch.object(MotionSensorManager, '_setup_gpiozero_pi5', return_value=False):
        manager = MotionSensorManager(config_manager=mock_config_manager)

        # Mock setup command success
        mock_subprocess.return_value = MagicMock(stdout='level=1')
        
        # Test motion detected
        assert manager.detect_motion() is True
        # Check that setup and get were called
        assert mock_subprocess.call_count == 2
        assert 'pinctrl' in mock_subprocess.call_args_list[0].args[0]
        assert 'set' in mock_subprocess.call_args_list[0].args[0]
        assert 'get' in mock_subprocess.call_args_list[1].args[0]

        # Test no motion
        mock_subprocess.reset_mock()
        mock_subprocess.return_value = MagicMock(stdout='level=0')
        assert manager.detect_motion() is False
        # Initialization should not happen again, only 'get' should be called
        assert mock_subprocess.call_count == 1
        assert 'get' in mock_subprocess.call_args_list[0].args[0]

        # Additional test to ensure correct initialization
        mock_subprocess.reset_mock()
        mock_subprocess.return_value = MagicMock(stdout='level=1')
        assert manager.detect_motion() is True
        # Check that only 'get' is called after initialization
        assert mock_subprocess.call_count == 1
        assert 'get' in mock_subprocess.call_args_list[0].args[0]

        mock_subprocess.reset_mock()
        mock_subprocess.return_value = MagicMock(stdout='4: ip    pd | hi // GPIO4 = input')
        assert manager.detect_motion() is True
        assert mock_subprocess.call_count == 1
        assert 'get' in mock_subprocess.call_args_list[0].args[0]

        # Additional test to ensure correct initialization
        mock_subprocess.reset_mock()
        mock_subprocess.return_value = MagicMock(stdout='level=0')
        assert manager.detect_motion() is False
        # Check that only 'get' is called after initialization
        assert mock_subprocess.call_count == 1
        assert 'get' in mock_subprocess.call_args_list[0].args[0]

        mock_subprocess.reset_mock()
        mock_subprocess.return_value = MagicMock(stdout='4: ip    pd | lo // GPIO4 = input')
        assert manager.detect_motion() is False
        assert mock_subprocess.call_count == 1
        assert 'get' in mock_subprocess.call_args_list[0].args[0]


@patch('pi_inventory_system.platform_info.is_raspberry_pi_5', return_value=False)
@patch('pi_inventory_system.platform_info.is_raspberry_pi', return_value=True)
def test_missing_rpi_gpio_on_real_pi_reports_failure(
    mock_check_pi,
    mock_check_pi5,
    mock_config_manager,
):
    """On a real Pi, missing RPi.GPIO must surface as a hardware failure.
    The old MockGPIO fallback made diagnostics report the sensor healthy
    while input() could never see motion."""
    with patch.dict(sys.modules, {'RPi': None, 'RPi.GPIO': None}):
        manager = MotionSensorManager(config_manager=mock_config_manager)

    assert manager.is_supported() is True   # platform supports it...
    assert manager.is_healthy() is False    # ...but hardware access failed
    assert manager.is_available() is False
    assert manager.detect_motion() is False
    assert "RPi.GPIO" in (manager.last_error or "")


@patch('pi_inventory_system.platform_info.is_raspberry_pi_5', return_value=True)
@patch('pi_inventory_system.platform_info.is_raspberry_pi', return_value=True)
def test_motion_pin_defaults_to_gpio4_when_config_pin_is_none(
    mock_check_pi,
    mock_check_pi5,
):
    config = MagicMock()
    config.get_hardware_config.return_value = {
        'motion_sensor': {'pin': None, 'enabled': True}
    }

    manager = MotionSensorManager(config_manager=config)

    assert manager._pin == 4

@pytest.mark.skip(reason="Hardware-dependent test")
def test_real_motion_detection():
    """Test actual motion detection with real hardware."""
    # This test requires actual hardware and should be skipped in CI
    result = MotionSensorManager().detect_motion()
    assert isinstance(result, bool)
