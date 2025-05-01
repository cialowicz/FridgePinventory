# Tests for voice recognition module

import pytest
from unittest.mock import patch, MagicMock
from pi_inventory_system.voice_recognition import recognize_speech_from_mic

def test_successful_recognition():
    """Test successful speech recognition."""
    mock_recognizer = MagicMock()
    mock_recognizer.recognize_google.return_value = "add chicken"
    
    with patch('pi_inventory_system.voice_recognition.sr.Recognizer', return_value=mock_recognizer), \
         patch('pi_inventory_system.voice_recognition.sr.Microphone') as mock_mic:
        result = recognize_speech_from_mic()
        assert result == "add chicken"

def test_recognition_error():
    """Test handling recognition error."""
    mock_recognizer = MagicMock()
    mock_recognizer.recognize_google.side_effect = Exception("Recognition error")
    
    with patch('pi_inventory_system.voice_recognition.sr.Recognizer', return_value=mock_recognizer), \
         patch('pi_inventory_system.voice_recognition.sr.Microphone') as mock_mic:
        result = recognize_speech_from_mic()
        assert result is None

def test_microphone_error():
    """Test handling microphone error."""
    with patch('pi_inventory_system.voice_recognition.sr.Recognizer') as mock_recognizer, \
         patch('pi_inventory_system.voice_recognition.sr.Microphone', side_effect=Exception("Mic error")):
        result = recognize_speech_from_mic()
        assert result is None
