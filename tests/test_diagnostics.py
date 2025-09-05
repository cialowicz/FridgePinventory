# Tests for diagnostics module

import pytest
from unittest.mock import patch, MagicMock, call
from pi_inventory_system.diagnostics import run_startup_diagnostics

@pytest.fixture
def mock_display():
    with patch('pi_inventory_system.diagnostics.initialize_display') as mock:
        mock_display = MagicMock()
        mock.return_value = mock_display
        yield mock_display

@pytest.fixture
def mock_motion_sensor():
    with patch('pi_inventory_system.diagnostics.detect_motion') as mock:
        mock.return_value = False
        yield mock

@pytest.fixture
def mock_supported():
    with patch('pi_inventory_system.diagnostics.is_display_supported') as mock_display, \
         patch('pi_inventory_system.diagnostics.is_motion_sensor_supported') as mock_motion:
        mock_display.return_value = True
        mock_motion.return_value = True
        yield mock_display, mock_motion

@pytest.fixture
def mock_config_manager():
    """Mock the config manager."""
    return MagicMock()

@pytest.fixture
def mock_audio():
    with patch('pi_inventory_system.diagnostics.AudioFeedbackManager') as mock_manager_class:
        mock_manager_instance = MagicMock()
        mock_manager_instance.play_sound.return_value = True
        mock_manager_class.return_value = mock_manager_instance
        yield mock_manager_instance

def test_diagnostics_display_success(mock_display, mock_motion_sensor, mock_supported, mock_audio, mock_config_manager):
    """Test successful display diagnostics."""
    with patch('pi_inventory_system.diagnostics.display_text') as mock_display_text:
        mock_display_text.return_value = True
        display_ok, motion_sensor_ok, audio_ok, display_instance = run_startup_diagnostics(mock_config_manager)
        assert display_ok is True
        assert motion_sensor_ok is True
        assert audio_ok is True
        
        expected_calls = [
            call(mock_display, "FridgePinventory\nstarting up...", config_manager=mock_config_manager),
            call(mock_display, "Diagnostics complete:\nDisplay: OK\nMotion: OK\nAudio: OK", config_manager=mock_config_manager)
        ]
        mock_display_text.assert_has_calls(expected_calls, any_order=False)

def test_diagnostics_display_failure(mock_display, mock_motion_sensor, mock_supported, mock_audio, mock_config_manager):
    """Test display diagnostics failure."""
    with patch('pi_inventory_system.diagnostics.display_text') as mock_display_text:
        mock_display_text.return_value = False
        display_ok, motion_sensor_ok, audio_ok, display_instance = run_startup_diagnostics(mock_config_manager)
        assert display_ok is False
        assert motion_sensor_ok is True
        assert audio_ok is True

def test_diagnostics_motion_sensor_failure(mock_display, mock_motion_sensor, mock_supported, mock_audio, mock_config_manager):
    """Test motion sensor diagnostics failure."""
    mock_motion_sensor.side_effect = Exception("Sensor error")
    with patch('pi_inventory_system.diagnostics.display_text') as mock_display_text:
        mock_display_text.return_value = True
        display_ok, motion_sensor_ok, audio_ok, display_instance = run_startup_diagnostics(mock_config_manager)
        assert display_ok is True
        assert motion_sensor_ok is False
        assert audio_ok is True

def test_diagnostics_platform_not_supported(mock_config_manager):
    """Test diagnostics on unsupported platform."""
    with patch('pi_inventory_system.diagnostics.is_display_supported') as mock_display, \
         patch('pi_inventory_system.diagnostics.is_motion_sensor_supported') as mock_motion:
        mock_display.return_value = False
        mock_motion.return_value = False
        display_ok, motion_sensor_ok, audio_ok, display_instance = run_startup_diagnostics(mock_config_manager)
        assert display_ok is False
        assert motion_sensor_ok is False
        assert audio_ok is True

def test_diagnostics_audio_success(mock_display, mock_motion_sensor, mock_supported, mock_audio, mock_config_manager):
    """Test successful audio diagnostics."""
    mock_audio.play_sound.return_value = True
    display_ok, motion_sensor_ok, audio_ok, display_instance = run_startup_diagnostics(mock_config_manager)
    assert audio_ok is True
    mock_audio.play_sound.assert_called_once_with('success')

def test_diagnostics_audio_failure(mock_display, mock_motion_sensor, mock_supported, mock_audio, mock_config_manager):
    """Test audio diagnostics failure."""
    mock_audio.play_sound.return_value = False
    display_ok, motion_sensor_ok, audio_ok, display_instance = run_startup_diagnostics(mock_config_manager)
    assert audio_ok is False
    mock_audio.play_sound.assert_called_once_with('success')
