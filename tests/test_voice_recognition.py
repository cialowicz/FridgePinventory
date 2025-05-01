# Tests for voice recognition module

import unittest
from unittest.mock import patch, MagicMock
from src.pi_inventory_system.voice_recognition import recognize_speech_from_mic


class TestVoiceRecognition(unittest.TestCase):
    """Test cases for voice recognition functionality."""

    def test_successful_recognition(self):
        """Test successful speech recognition."""
        mock_recognizer = MagicMock()
        mock_recognizer.recognize_google.return_value = "add chicken"
        
        with patch('src.pi_inventory_system.voice_recognition.sr.Recognizer', return_value=mock_recognizer), \
             patch('src.pi_inventory_system.voice_recognition.sr.Microphone') as mock_mic:
            result = recognize_speech_from_mic()
            self.assertEqual(result, "add chicken")

    def test_recognition_error(self):
        """Test handling recognition error."""
        mock_recognizer = MagicMock()
        mock_recognizer.recognize_google.side_effect = Exception("Recognition error")
        
        with patch('src.pi_inventory_system.voice_recognition.sr.Recognizer', return_value=mock_recognizer), \
             patch('src.pi_inventory_system.voice_recognition.sr.Microphone') as mock_mic:
            result = recognize_speech_from_mic()
            self.assertIsNone(result)

    def test_microphone_error(self):
        """Test handling microphone error."""
        with patch('src.pi_inventory_system.voice_recognition.sr.Recognizer') as mock_recognizer, \
             patch('src.pi_inventory_system.voice_recognition.sr.Microphone', side_effect=Exception("Mic error")):
            result = recognize_speech_from_mic()
            self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
