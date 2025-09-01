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
def mock_audio():
    with patch('pi_inventory_system.diagnostics.play_feedback_sound') as mock_sound, \
         patch('pi_inventory_system.diagnostics.pyttsx3.init') as mock_tts, \
         patch('pi_inventory_system.diagnostics.recognize_speech_from_mic') as mock_mic:
        mock_sound.return_value = True
        mock_tts.return_value = MagicMock()
        mock_mic.return_value = "test"
        yield mock_sound, mock_tts, mock_mic

def test_diagnostics_display_success(mock_display, mock_motion_sensor, mock_supported, mock_audio):
    """Test successful display diagnostics."""
    with patch('pi_inventory_system.diagnostics.display_text') as mock_display_text:
        mock_display_text.return_value = True
        display_ok, motion_sensor_ok, audio_ok, display_instance = run_startup_diagnostics()
        assert display_ok is True
        assert motion_sensor_ok is True
        assert audio_ok is True
        
        # Check that display_text was called with both messages
        expected_calls = [
            (mock_display, "FridgePinventory\nstarting up..."),
            (mock_display, "Diagnostics complete:\nDisplay: OK\nMotion: OK\nAudio: OK")
        ]
        actual_calls = [call[0] for call in mock_display_text.call_args_list]
        assert actual_calls == expected_calls

def test_diagnostics_display_failure(mock_display, mock_motion_sensor, mock_supported, mock_audio):
    """Test display diagnostics failure."""
    with patch('pi_inventory_system.diagnostics.display_text') as mock_display_text:
        mock_display_text.return_value = False
        display_ok, motion_sensor_ok, audio_ok, display_instance = run_startup_diagnostics()
        assert display_ok is False
        assert motion_sensor_ok is True
        assert audio_ok is True

def test_diagnostics_motion_sensor_failure(mock_display, mock_motion_sensor, mock_supported, mock_audio):
    """Test motion sensor diagnostics failure."""
    mock_motion_sensor.side_effect = Exception("Sensor error")
    with patch('pi_inventory_system.diagnostics.display_text') as mock_display_text:
        mock_display_text.return_value = True
        display_ok, motion_sensor_ok, audio_ok, display_instance = run_startup_diagnostics()
        assert display_ok is True
        assert motion_sensor_ok is False
        assert audio_ok is True

def test_diagnostics_platform_not_supported():
    """Test diagnostics on unsupported platform."""
    with patch('pi_inventory_system.diagnostics.is_display_supported') as mock_display, \
         patch('pi_inventory_system.diagnostics.is_motion_sensor_supported') as mock_motion:
        mock_display.return_value = False
        mock_motion.return_value = False
        display_ok, motion_sensor_ok, audio_ok, display_instance = run_startup_diagnostics()
        assert display_ok is False
        assert motion_sensor_ok is False
        assert audio_ok is False

def test_diagnostics_audio_success(mock_display, mock_motion_sensor, mock_supported):
    """Test successful audio diagnostics."""
    with patch('pi_inventory_system.diagnostics.display_text') as mock_display_text, \
         patch('pi_inventory_system.diagnostics.play_feedback_sound') as mock_sound, \
         patch('pi_inventory_system.diagnostics.pyttsx3.init') as mock_tts, \
         patch('pi_inventory_system.diagnostics.recognize_speech_from_mic') as mock_mic:
        mock_display_text.return_value = True
        mock_sound.return_value = True
        mock_tts.return_value = MagicMock()
        mock_mic.return_value = "test"
        display_ok, motion_sensor_ok, audio_ok, display_instance = run_startup_diagnostics()
        assert display_ok is True
        assert motion_sensor_ok is True
        assert audio_ok is True
        assert mock_sound.call_count == 2  # Called for success sound and test completion

def test_diagnostics_audio_failure(mock_display, mock_motion_sensor, mock_supported):
    """Test audio diagnostics failure."""
    with patch('pi_inventory_system.diagnostics.display_text') as mock_display_text, \
         patch('pi_inventory_system.diagnostics.play_feedback_sound') as mock_sound, \
         patch('pi_inventory_system.diagnostics.pyttsx3.init') as mock_tts, \
         patch('pi_inventory_system.diagnostics.recognize_speech_from_mic') as mock_mic:
        mock_display_text.return_value = True
        mock_sound.return_value = False
        mock_tts.return_value = MagicMock()
        mock_mic.return_value = None
        display_ok, motion_sensor_ok, audio_ok, display_instance = run_startup_diagnostics()
        assert display_ok is True
        assert motion_sensor_ok is True
        assert audio_ok is False
        assert mock_sound.call_count == 2  # Called for initial attempt and error sound 
