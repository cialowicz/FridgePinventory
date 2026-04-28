from unittest.mock import MagicMock, patch

from pi_inventory_system.voice_recognition_manager import VoiceRecognitionManager


def _config(cooldown):
    cfg = MagicMock()
    cfg.get_audio_config.return_value = {
        'voice_recognition': {
            'initialization_retry_cooldown': cooldown,
            'timeout': 5,
            'phrase_time_limit': 10,
            'engine': 'sphinx',
        }
    }
    return cfg


def _microphone():
    mic = MagicMock()
    mic.__enter__.return_value = MagicMock()
    mic.__exit__.return_value = False
    return mic


def test_initialization_retries_after_cooldown():
    cfg = _config(cooldown=0)
    recognizer = MagicMock()
    mic = _microphone()

    with patch('pi_inventory_system.voice_recognition_manager.sr.Recognizer',
               return_value=recognizer), \
         patch('pi_inventory_system.voice_recognition_manager.sr.Microphone',
               side_effect=[OSError("missing"), OSError("missing"), OSError("missing"), mic]):
        manager = VoiceRecognitionManager(config_manager=cfg)

        assert manager.initialize() is False
        assert manager.initialize() is False
        assert manager.initialize() is False
        assert manager._initialization_failed is True

        assert manager.initialize() is True
        assert manager._initialization_failed is False
        assert manager._retry_count == 0


def test_initialization_failure_respects_retry_cooldown():
    cfg = _config(cooldown=60)

    with patch('pi_inventory_system.voice_recognition_manager.sr.Microphone',
               side_effect=OSError("missing")) as microphone:
        manager = VoiceRecognitionManager(config_manager=cfg)

        assert manager.initialize() is False
        assert manager.initialize() is False
        assert manager.initialize() is False
        assert manager._initialization_failed is True

        assert manager.initialize() is False
        assert microphone.call_count == 3
