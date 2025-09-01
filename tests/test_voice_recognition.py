# Tests for voice recognition module

import pytest
from unittest.mock import patch, MagicMock
import speech_recognition as sr
from pi_inventory_system.voice_recognition import recognize_speech_from_mic

@pytest.fixture(autouse=True)
def reset_audio_components():
    """Reset global audio components before each test to prevent state leakage."""
    # By patching the module-level variables, we ensure each test gets a fresh start
    with patch('pi_inventory_system.voice_recognition.recognizer', None), \
         patch('pi_inventory_system.voice_recognition.microphone', None):
        yield

def test_successful_recognition():
    """Test successful speech recognition."""
    mock_recognizer = MagicMock()
    mock_recognizer.recognize_sphinx.return_value = "add chicken"
    
    with patch('pi_inventory_system.voice_recognition.sr.Recognizer', return_value=mock_recognizer), \
         patch('pi_inventory_system.voice_recognition.sr.Microphone') as mock_mic:
        result = recognize_speech_from_mic()
        assert result == "add chicken"

def test_recognition_error_unknown_value():
    """Test handling sr.UnknownValueError during recognition."""
    mock_recognizer = MagicMock()
    mock_recognizer.recognize_sphinx.side_effect = sr.UnknownValueError()

    with patch('pi_inventory_system.voice_recognition.sr.Recognizer', return_value=mock_recognizer), \
         patch('pi_inventory_system.voice_recognition.sr.Microphone'):
        result = recognize_speech_from_mic()
        assert result is None

def test_recognition_error_request_error():
    """Test handling sr.RequestError during recognition."""
    mock_recognizer = MagicMock()
    mock_recognizer.recognize_sphinx.side_effect = sr.RequestError("API error")

    with patch('pi_inventory_system.voice_recognition.sr.Recognizer', return_value=mock_recognizer), \
         patch('pi_inventory_system.voice_recognition.sr.Microphone'):
        result = recognize_speech_from_mic()
        assert result is None

def test_microphone_initialization_error():
    """Test handling a failure in the audio component initialization."""
    # This is a more realistic test of microphone failure, as it simulates the init function failing
    with patch('pi_inventory_system.voice_recognition._initialize_audio_components', return_value=False):
        result = recognize_speech_from_mic()
        assert result is None
