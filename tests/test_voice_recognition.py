# Tests for voice recognition module

import unittest
from unittest.mock import patch, MagicMock
from pi_inventory_system.voice_recognition import recognize_speech_from_mic
import speech_recognition as sr


class TestVoiceRecognition(unittest.TestCase):

    @patch('pi_inventory_system.voice_recognition.sr')
    def test_successful_recognition(self, mock_sr):
        # Setup mock recognizer
        mock_recognizer = MagicMock()
        mock_sr.Recognizer.return_value = mock_recognizer
        mock_recognizer.recognize_google.return_value = "test command"

        # Call function
        result = recognize_speech_from_mic()
        self.assertEqual(result, "test command")

    @patch('pi_inventory_system.voice_recognition.sr')
    def test_unknown_audio(self, mock_sr):
        # Setup mock recognizer
        mock_recognizer = MagicMock()
        mock_sr.Recognizer.return_value = mock_recognizer
        mock_recognizer.recognize_google.side_effect = sr.UnknownValueError()

        # Call function
        result = recognize_speech_from_mic()
        self.assertIsNone(result)

    @patch('pi_inventory_system.voice_recognition.sr')
    def test_request_error(self, mock_sr):
        # Setup mock recognizer
        mock_recognizer = MagicMock()
        mock_sr.Recognizer.return_value = mock_recognizer
        mock_recognizer.recognize_google.side_effect = sr.RequestError()

        # Call function
        result = recognize_speech_from_mic()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
