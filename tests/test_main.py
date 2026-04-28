import time
from unittest.mock import MagicMock, patch

import pytest

from pi_inventory_system.main import FridgePinventoryApp


@pytest.fixture
def app_context():
    cfg = MagicMock()
    cfg.get_system_config.return_value = {
        'log_level': 'INFO',
        'motion_check_interval': 0.5,
        'idle_delay': 1.0,
        'main_loop_delay': 0.1,
    }
    db = MagicMock()

    with patch('pi_inventory_system.main.create_config_manager', return_value=cfg) as create_cfg, \
         patch('pi_inventory_system.main.create_database_manager', return_value=db) as create_db, \
         patch('pi_inventory_system.main.MotionSensorManager') as motion_cls, \
         patch('pi_inventory_system.main.VoiceRecognitionManager') as voice_cls, \
         patch('pi_inventory_system.main.AudioFeedbackManager') as audio_cls, \
         patch('pi_inventory_system.main.signal.signal'):
        motion = MagicMock()
        voice = MagicMock()
        audio = MagicMock()
        motion_cls.return_value = motion
        voice_cls.return_value = voice
        audio_cls.return_value = audio

        app = FridgePinventoryApp(config_path="custom.yaml", db_path="custom.db")
        yield app, cfg, db, create_cfg, create_db, motion, voice, audio
        app._cleanup()


def test_app_uses_provided_config_path(app_context):
    _, cfg, _, create_cfg, create_db, _, _, _ = app_context

    create_cfg.assert_called_once_with("custom.yaml")
    create_db.assert_called_once_with(cfg, db_path="custom.db")


def test_initialize_reuses_runtime_managers_for_diagnostics(app_context):
    app, cfg, _, _, _, motion, _, audio = app_context

    with patch('pi_inventory_system.main.run_startup_diagnostics',
               return_value=(False, True, False, None)) as diagnostics:
        assert app.initialize() is True

    diagnostics.assert_called_once_with(
        cfg,
        motion_manager=motion,
        audio_manager=audio,
    )


def test_handle_voice_command_outputs_confirmation(app_context):
    app, _, _, _, _, _, voice, audio = app_context
    app.running = True
    app.controller = MagicMock()
    voice.recognize_speech.return_value = "add 1 salmon"
    app.controller.process_command.return_value = (True, "salmon now has 1 in inventory.")

    app._handle_voice_command(display_ok=True)

    audio.output_confirmation.assert_called_once_with("salmon now has 1 in inventory.")
    audio.output_error.assert_not_called()


def test_handle_voice_command_outputs_error(app_context):
    app, _, _, _, _, _, voice, audio = app_context
    app.running = True
    app.controller = MagicMock()
    voice.recognize_speech.return_value = "remove 1 salmon"
    app.controller.process_command.return_value = (False, "salmon is not in inventory.")

    app._handle_voice_command(display_ok=True)

    audio.output_error.assert_called_once_with("salmon is not in inventory.")
    audio.output_confirmation.assert_not_called()


def test_kick_voice_command_does_not_block_motion_loop(app_context):
    app, _, _, _, _, _, _, _ = app_context

    def slow_voice_command(_display_ok):
        time.sleep(0.2)

    app._handle_voice_command = slow_voice_command

    started = time.monotonic()
    app._kick_voice_command(display_ok=True)
    elapsed = time.monotonic() - started

    assert elapsed < 0.1
    assert app._check_voice_future() is True
    app._voice_future.result(timeout=1)
    assert app._check_voice_future() is False


def test_run_processes_motion_transition_and_cleans_up(app_context):
    app, _, _, _, _, motion, _, _ = app_context
    motion.detect_motion.return_value = True

    def stop_after_voice(_display_ok):
        app.running = False
        app.shutdown_event.set()

    app._kick_voice_command = MagicMock(side_effect=stop_after_voice)

    with patch('pi_inventory_system.main.run_startup_diagnostics',
               return_value=(False, True, False, None)):
        app.run()

    app._kick_voice_command.assert_called_once_with(False)
    motion.cleanup.assert_called()
