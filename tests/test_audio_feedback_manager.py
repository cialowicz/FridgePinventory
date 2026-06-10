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


def test_output_confirmation_combines_speech_and_success_sound(cfg):
    with patch('pi_inventory_system.audio_feedback_manager.PYTTSX3_AVAILABLE', False):
        manager = AudioFeedbackManager(config_manager=cfg)
    manager.speak = MagicMock(return_value=True)
    manager.play_sound = MagicMock(return_value=True)

    assert manager.output_confirmation("added salmon") is True
    manager.speak.assert_called_once_with("added salmon")
    manager.play_sound.assert_called_once_with('success')


def test_output_error_reports_failure_when_sound_fails(cfg):
    with patch('pi_inventory_system.audio_feedback_manager.PYTTSX3_AVAILABLE', False):
        manager = AudioFeedbackManager(config_manager=cfg)
    manager.speak = MagicMock(return_value=True)
    manager.play_sound = MagicMock(return_value=False)

    assert manager.output_error("bad command") is False
    manager.speak.assert_called_once_with("bad command")
    manager.play_sound.assert_called_once_with('error')


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


@pytest.mark.parametrize("method,sound", [
    ("output_confirmation", "success"),
    ("output_error", "error"),
])
def test_output_plays_chime_before_speech(cfg, method, sound):
    """The chime is the attention cue; it must precede the spoken message,
    not fire over it while the async TTS worker is still dequeuing."""
    with patch('pi_inventory_system.audio_feedback_manager.PYTTSX3_AVAILABLE', False):
        manager = AudioFeedbackManager(config_manager=cfg)
    order = []
    manager.play_sound = MagicMock(side_effect=lambda t: order.append(('sound', t)) or True)
    manager.speak = MagicMock(side_effect=lambda m: order.append(('speak', m)) or True)

    assert getattr(manager, method)("message") is True

    assert order == [('sound', sound), ('speak', 'message')]


def test_play_wav_aplay_fallback_has_timeout(tmp_path):
    """A hung aplay process must not block the sound lock forever."""
    from pi_inventory_system import audio_feedback_manager as afm

    wav = tmp_path / "s.wav"
    wav.write_bytes(b"RIFF")
    with patch.object(afm, 'SIMPLEAUDIO_AVAILABLE', False), \
         patch.object(afm.shutil, 'which', return_value='/usr/bin/aplay'), \
         patch.object(afm.subprocess, 'run') as run:
        afm._play_wav_file(str(wav))

    timeout = run.call_args.kwargs.get('timeout')
    assert isinstance(timeout, (int, float)) and timeout > 0
