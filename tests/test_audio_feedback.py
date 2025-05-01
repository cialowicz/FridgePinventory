# Tests for audio feedback module

import pytest
from unittest.mock import patch
from pi_inventory_system.audio_feedback import play_feedback_sound, output_confirmation

def test_play_feedback_sound_success():
    """Test playing success feedback sound."""
    with patch('pi_inventory_system.audio_feedback.playsound') as mock_playsound:
        play_feedback_sound(True)
        mock_playsound.assert_called_once_with('sounds/success.wav')

def test_play_feedback_sound_error():
    """Test playing error feedback sound."""
    with patch('pi_inventory_system.audio_feedback.playsound') as mock_playsound:
        play_feedback_sound(False)
        mock_playsound.assert_called_once_with('sounds/error.wav')

def test_play_feedback_sound_fallback():
    """Test fallback when playsound fails."""
    with patch('pi_inventory_system.audio_feedback.playsound') as mock_playsound:
        mock_playsound.side_effect = Exception("Audio error")
        # Should not raise an exception
        play_feedback_sound(True)
        play_feedback_sound(False)

def test_output_confirmation():
    """Test outputting confirmation message."""
    test_message = "Test confirmation message"
    with patch('builtins.print') as mock_print:
        output_confirmation(test_message)
        mock_print.assert_called_once_with(f"Confirmation: {test_message}")
