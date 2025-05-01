# Tests for audio feedback module

import unittest
from unittest.mock import patch
from src.pi_inventory_system.audio_feedback import play_feedback_sound, output_confirmation


class TestAudioFeedback(unittest.TestCase):
    """Test cases for audio feedback functionality."""

    def test_play_feedback_sound_success(self):
        """Test playing success feedback sound."""
        with patch('src.pi_inventory_system.audio_feedback.playsound') as mock_playsound:
            play_feedback_sound(True)
            mock_playsound.assert_called_once_with('sounds/success.wav')

    def test_play_feedback_sound_error(self):
        """Test playing error feedback sound."""
        with patch('src.pi_inventory_system.audio_feedback.playsound') as mock_playsound:
            play_feedback_sound(False)
            mock_playsound.assert_called_once_with('sounds/error.wav')

    def test_play_feedback_sound_fallback(self):
        """Test fallback when playsound fails."""
        with patch('src.pi_inventory_system.audio_feedback.playsound') as mock_playsound:
            mock_playsound.side_effect = Exception("Audio error")
            # Should not raise an exception
            play_feedback_sound(True)
            play_feedback_sound(False)

    def test_output_confirmation(self):
        """Test outputting confirmation message."""
        test_message = "Test confirmation message"
        with patch('builtins.print') as mock_print:
            output_confirmation(test_message)
            mock_print.assert_called_once_with(f"Confirmation: {test_message}")


if __name__ == '__main__':
    unittest.main()
