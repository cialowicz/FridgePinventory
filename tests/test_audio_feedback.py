# Tests for audio feedback module

import unittest
from unittest.mock import patch, MagicMock
from pi_inventory_system.audio_feedback import play_feedback_sound, output_confirmation


class TestAudioFeedback(unittest.TestCase):

    @patch('builtins.print')
    def test_audio_feedback_on_success(self, mock_print):
        """Test feedback output on successful operation."""
        result = play_feedback_sound(True)
        self.assertTrue(result)
        mock_print.assert_called_once_with("Success")

    @patch('builtins.print')
    def test_audio_feedback_on_failure(self, mock_print):
        """Test feedback output on failed operation."""
        result = play_feedback_sound(False)
        self.assertFalse(result)
        mock_print.assert_called_once_with("Error")

    @patch('builtins.print')
    def test_confirmation_with_message(self, mock_print):
        """Test confirmation output with a valid message."""
        result = output_confirmation("Test message")
        self.assertTrue(result)
        mock_print.assert_called_once_with("Confirmation: Test message")

    @patch('builtins.print')
    def test_confirmation_with_empty_message(self, mock_print):
        """Test confirmation output with an empty message."""
        result = output_confirmation("")
        self.assertFalse(result)
        mock_print.assert_not_called()


if __name__ == '__main__':
    unittest.main()
