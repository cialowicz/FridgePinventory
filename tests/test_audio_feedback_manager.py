"""Tests for AudioFeedbackManager — circuit breaker and missing-file paths."""

from unittest.mock import MagicMock, patch

import pytest

from pi_inventory_system.audio_feedback_manager import AudioFeedbackManager


@pytest.fixture
def cfg():
    cm = MagicMock()
    cm.get_audio_config.return_value = {
        'feedback_sounds': {
            'success_sound': '/nope/success.wav',
            'error_sound': '/nope/error.wav',
        },
        'text_to_speech': {'rate': 150, 'volume': 0.9, 'voice_id': None},
    }
    return cm


def test_play_sound_returns_false_when_file_missing(cfg):
    with patch('pi_inventory_system.audio_feedback_manager.PYTTSX3_AVAILABLE', False), \
         patch('pi_inventory_system.audio_feedback_manager.SIMPLEAUDIO_AVAILABLE', True):
        manager = AudioFeedbackManager(config_manager=cfg)
        assert manager.play_sound('success') is False


def test_play_sound_returns_false_when_unknown_type(cfg):
    with patch('pi_inventory_system.audio_feedback_manager.PYTTSX3_AVAILABLE', False), \
         patch('pi_inventory_system.audio_feedback_manager.SIMPLEAUDIO_AVAILABLE', True):
        manager = AudioFeedbackManager(config_manager=cfg)
        assert manager.play_sound('rocketlaunch') is False


def test_warning_sound_falls_back_to_error_sound(cfg, tmp_path):
    error_sound = tmp_path / "error.wav"
    error_sound.write_bytes(b"RIFF")
    cfg.get_audio_config.return_value = {
        'feedback_sounds': {'error_sound': str(error_sound)},
        'text_to_speech': {'rate': 150, 'volume': 0.9, 'voice_id': None},
    }

    with patch('pi_inventory_system.audio_feedback_manager.PYTTSX3_AVAILABLE', False), \
         patch('pi_inventory_system.audio_feedback_manager.SIMPLEAUDIO_AVAILABLE', True), \
         patch('pi_inventory_system.audio_feedback_manager._play_wav_file') as play_wav:
        manager = AudioFeedbackManager(config_manager=cfg)
        assert manager.play_sound('warning') is True
        play_wav.assert_called_once_with(str(error_sound))


def test_play_sound_returns_false_when_no_backend(cfg):
    with patch('pi_inventory_system.audio_feedback_manager.PYTTSX3_AVAILABLE', False), \
         patch('pi_inventory_system.audio_feedback_manager.SIMPLEAUDIO_AVAILABLE', False), \
         patch('pi_inventory_system.audio_feedback_manager.shutil.which', return_value=None):
        manager = AudioFeedbackManager(config_manager=cfg)
        assert manager.play_sound('success') is False


def test_speak_returns_false_when_tts_unavailable(cfg):
    with patch('pi_inventory_system.audio_feedback_manager.PYTTSX3_AVAILABLE', False):
        manager = AudioFeedbackManager(config_manager=cfg)
        assert manager.speak("hello") is False


def test_speak_returns_false_when_tts_initialization_fails(cfg):
    with patch('pi_inventory_system.audio_feedback_manager.PYTTSX3_AVAILABLE', True), \
         patch.object(AudioFeedbackManager, '_initialize_tts', return_value=False):
        manager = AudioFeedbackManager(config_manager=cfg)
        assert manager.speak("hello") is False


def test_circuit_breaker_disables_after_repeated_failures(cfg, tmp_path):
    sound = tmp_path / "s.wav"
    sound.write_bytes(b"")
    cfg.get_audio_config.return_value = {
        'feedback_sounds': {'success_sound': str(sound)},
        'text_to_speech': {'rate': 150, 'volume': 0.9, 'voice_id': None},
    }
    with patch('pi_inventory_system.audio_feedback_manager.PYTTSX3_AVAILABLE', False), \
         patch('pi_inventory_system.audio_feedback_manager.SIMPLEAUDIO_AVAILABLE', True), \
         patch('pi_inventory_system.audio_feedback_manager._play_wav_file',
               side_effect=RuntimeError("bad")):
        manager = AudioFeedbackManager(config_manager=cfg)
        for _ in range(3):
            manager.play_sound('success')
        assert manager._sound_disabled is True
        assert manager.play_sound('success') is False
