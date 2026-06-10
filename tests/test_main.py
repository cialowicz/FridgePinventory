import time
from unittest.mock import MagicMock, patch

import pytest

from pi_inventory_system.main import (
    MAX_ORPHANED_VOICE_TASKS,
    FridgePinventoryApp,
)


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
         patch('signal.signal'):
        motion = MagicMock(name="motion")
        audio = MagicMock(name="audio")
        # Each call to the patched class returns a new mock so retire produces
        # a distinct successor from the original.
        voice = MagicMock(name="voice_initial")
        voice_cls.side_effect = [
            voice,
            MagicMock(name="voice_replacement_1"),
            MagicMock(name="voice_replacement_2"),
        ]
        motion_cls.return_value = motion
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

    app._handle_voice_command()

    audio.output_confirmation.assert_called_once_with("salmon now has 1 in inventory.")
    audio.output_error.assert_not_called()


def test_handle_voice_command_outputs_error(app_context):
    app, _, _, _, _, _, voice, audio = app_context
    app.running = True
    app.controller = MagicMock()
    voice.recognize_speech.return_value = "remove 1 salmon"
    app.controller.process_command.return_value = (False, "salmon is not in inventory.")

    app._handle_voice_command()

    audio.output_error.assert_called_once_with("salmon is not in inventory.")
    audio.output_confirmation.assert_not_called()


def test_handle_voice_command_exception_outputs_error_feedback(app_context):
    app, _, _, _, _, _, voice, audio = app_context
    app.running = True
    app.controller = MagicMock()
    voice.recognize_speech.side_effect = RuntimeError("mic exploded")

    app._handle_voice_command()

    audio.output_error.assert_called_once_with("Voice command failed. Please try again.")


def test_continue_listening_kicks_within_window(app_context):
    app, *_ = app_context
    loop = MagicMock()
    loop.last_motion_time = time.time() - 5  # within the default 20s window

    with patch.object(app, '_kick_voice_command') as kick:
        app._maybe_continue_listening(loop)

    kick.assert_called_once()


def test_continue_listening_stops_after_window_expires(app_context):
    app, *_ = app_context
    loop = MagicMock()
    loop.last_motion_time = time.time() - 25  # past the default 20s window

    with patch.object(app, '_kick_voice_command') as kick:
        app._maybe_continue_listening(loop)

    kick.assert_not_called()


def test_continue_listening_window_is_configurable(app_context):
    app, cfg, *_ = app_context
    cfg.get_system_config.return_value = {
        **cfg.get_system_config.return_value,
        'listen_window_seconds': 2.0,
    }
    loop = MagicMock()
    loop.last_motion_time = time.time() - 5

    with patch.object(app, '_kick_voice_command') as kick:
        app._maybe_continue_listening(loop)

    kick.assert_not_called()


def test_continue_listening_skips_before_any_motion(app_context):
    app, *_ = app_context
    loop = MagicMock()
    loop.last_motion_time = None

    with patch.object(app, '_kick_voice_command') as kick:
        app._maybe_continue_listening(loop)

    kick.assert_not_called()


def test_continue_listening_skips_while_voice_task_running(app_context):
    app, *_ = app_context
    running = MagicMock()
    running.done.return_value = False
    app._voice_future = running
    app._voice_started_at = time.monotonic()
    loop = MagicMock()
    loop.last_motion_time = time.time()

    with patch.object(app, '_kick_voice_command') as kick:
        app._maybe_continue_listening(loop)

    kick.assert_not_called()
    app._voice_future = None


def test_continue_listening_respects_rekick_gap(app_context):
    app, *_ = app_context
    loop = MagicMock()
    loop.last_motion_time = time.time()

    app._last_voice_kick_at = time.monotonic()
    with patch.object(app, '_kick_voice_command') as kick:
        app._maybe_continue_listening(loop)
    kick.assert_not_called()

    app._last_voice_kick_at = time.monotonic() - 5
    with patch.object(app, '_kick_voice_command') as kick:
        app._maybe_continue_listening(loop)
    kick.assert_called_once()


def test_kick_voice_command_records_kick_time(app_context):
    app, *_ = app_context

    assert app._last_voice_kick_at is None
    app._kick_voice_command()
    assert app._last_voice_kick_at is not None
    assert app._voice_future is not None
    app._voice_future.result(timeout=2)


def test_kick_voice_command_does_not_block_motion_loop(app_context):
    app, _, _, _, _, _, _, _ = app_context

    def slow_voice_command(_voice_manager=None):
        time.sleep(0.2)

    app._handle_voice_command = slow_voice_command

    started = time.monotonic()
    app._kick_voice_command()
    elapsed = time.monotonic() - started

    assert elapsed < 0.1
    assert app._check_voice_future() is True
    app._voice_future.result(timeout=1)
    assert app._check_voice_future() is False


def test_voice_timeout_derived_from_config(app_context):
    """The worker deadline must cover listen timeout + phrase window + a
    recognition grace period, all taken from config."""
    app, cfg, _, _, _, _, _, _ = app_context
    cfg.get_audio_config.return_value = {
        'voice_recognition': {
            'timeout': 7,
            'phrase_time_limit': 20,
            'recognition_grace': 3,
        }
    }

    assert app._voice_timeout_seconds() == 30.0


def test_voice_timeout_defaults_exceed_listen_windows(app_context):
    """With default config (5s listen + 10s phrase) the deadline must leave
    real time for recognition itself — the old hardcoded 15s left zero."""
    app, cfg, _, _, _, _, _, _ = app_context
    cfg.get_audio_config.return_value = {}

    assert app._voice_timeout_seconds() >= 25.0


def test_voice_worker_not_retired_during_legitimate_phrase(app_context):
    """A worker 20s in (user spoke through the 10s phrase window, sphinx is
    decoding) is healthy and must not be retired with default config."""
    app, cfg, _, _, _, _, _, _ = app_context
    cfg.get_audio_config.return_value = {}
    future = MagicMock()
    future.done.return_value = False
    app._voice_future = future
    app._voice_started_at = time.monotonic() - 20

    assert app._check_voice_future() is True

    assert app._voice_future is future
    assert app._orphaned_voice_tasks == []
    assert app._voice_disabled is False


def test_voice_timeout_retires_worker(app_context):
    app, _, _, _, _, _, old_voice, _ = app_context
    future = MagicMock()
    future.done.return_value = False
    app._voice_future = future
    app._voice_started_at = time.monotonic() - app._voice_timeout_seconds() - 1

    assert app._check_voice_future() is False

    old_voice.cleanup.assert_not_called()
    assert app._voice_future is None
    assert future in app._orphaned_voice_tasks
    assert (future, old_voice) in app._orphaned_voice_managers
    # The fresh worker is functional and is the new owned manager.
    assert app._owned_voice_manager is app.voice_manager
    assert app._owned_voice_manager is not old_voice
    assert app._voice_disabled is False


def test_prune_orphaned_voice_task_cleans_retired_manager(app_context):
    app, _, _, _, _, _, old_voice, _ = app_context
    future = MagicMock()
    future.done.return_value = False
    app._voice_future = future
    app._voice_started_at = time.monotonic() - app._voice_timeout_seconds() - 1

    assert app._check_voice_future() is False
    old_voice.cleanup.assert_not_called()

    future.done.return_value = True
    app._prune_orphaned_voice_tasks()

    old_voice.cleanup.assert_called_once()
    assert app._orphaned_voice_tasks == []
    assert app._orphaned_voice_managers == []


def test_voice_timeout_disables_after_orphan_cap(app_context):
    app, _, _, _, _, _, _, _ = app_context

    for _ in range(MAX_ORPHANED_VOICE_TASKS):
        future = MagicMock()
        future.done.return_value = False
        app._voice_future = future
        app._voice_started_at = time.monotonic() - app._voice_timeout_seconds() - 1

        assert app._check_voice_future() is False

    assert len(app._orphaned_voice_tasks) == MAX_ORPHANED_VOICE_TASKS
    assert app._voice_disabled is True
    assert app._owned_voice_manager is None


def test_handle_voice_command_uses_warning_chime_on_removal(app_context):
    """A successful command that left the item at 0 should NOT play the
    success chime — that confuses 'I added it' with 'I emptied it'."""
    app, _, _, _, _, _, voice, audio = app_context
    app.running = True
    app.controller = MagicMock()
    voice.recognize_speech.return_value = "remove all salmon"
    app.controller.process_command.return_value = (
        True, "salmon has been removed from inventory.")

    app._handle_voice_command()

    audio.speak.assert_called_once_with("salmon has been removed from inventory.")
    audio.play_sound.assert_called_once_with('warning')
    audio.output_confirmation.assert_not_called()


def test_cleanup_waits_for_voice_worker_before_closing_db(app_context):
    """_cleanup must drain the voice worker before tearing down the DB."""
    app, _, db, _, _, motion, voice, audio = app_context

    voice_done = []

    fake_future = MagicMock()

    def slow_result(timeout=None):
        # Mimic a worker finishing just inside the cleanup timeout.
        voice_done.append(("future_drained", time.monotonic()))
        return None

    fake_future.result.side_effect = slow_result
    app._voice_future = fake_future

    # Track ordering: voice future must drain before db.cleanup runs.
    db.cleanup.side_effect = lambda: voice_done.append(("db_closed", time.monotonic()))

    app._cleanup()

    # Both events fired and in the right order.
    assert [e[0] for e in voice_done] == ["future_drained", "db_closed"]


def test_cleanup_skips_voice_manager_cleanup_when_worker_still_hung(app_context):
    app, _, db, _, _, _, voice, audio = app_context

    fake_future = MagicMock()
    fake_future.done.return_value = False
    fake_future.result.side_effect = TimeoutError("worker still running")
    app._voice_future = fake_future

    app._cleanup()

    voice.cleanup.assert_not_called()
    audio.cleanup.assert_called()
    db.cleanup.assert_called()


def test_cleanup_handles_voice_worker_timeout(app_context):
    """If the voice worker is still hung at cleanup time, log and proceed
    rather than blocking shutdown forever."""
    app, _, db, _, _, _, _, _ = app_context

    fake_future = MagicMock()
    fake_future.result.side_effect = TimeoutError("worker still running")
    app._voice_future = fake_future

    app._cleanup()

    db.cleanup.assert_called_once()


def test_initialize_resets_audio_circuit_breakers(app_context):
    app, _, _, _, _, _, _, audio = app_context
    with patch('pi_inventory_system.main.run_startup_diagnostics',
               return_value=(False, True, True, None)):
        app.initialize()
    audio.reset_circuit_breakers.assert_called_once()


def test_voice_task_after_retire_runs_followup_command(app_context):
    """After a retire, a freshly submitted voice command must complete."""
    app, _, _, _, _, _, old_voice, audio = app_context
    app.controller = MagicMock()
    app.running = True

    # Force a retire.
    app._voice_started_at = time.monotonic() - app._voice_timeout_seconds() - 1
    future_stub = MagicMock()
    future_stub.done.return_value = False
    app._voice_future = future_stub
    assert app._check_voice_future() is False

    # Wire the *new* manager to a successful recognition.
    new_voice = app.voice_manager
    new_voice.recognize_speech.return_value = "add 1 salmon"
    app.controller.process_command.return_value = (True, "salmon now has 1 in inventory.")

    app._kick_voice_command()
    app._voice_future.result(timeout=1)

    audio.output_confirmation.assert_called_once()


def test_voice_command_emits_one_display_refresh(app_context):
    """A successful voice command renders the display exactly once
    (process_command refreshes; the motion-active branch defers to the cache)."""
    app, _, _, _, _, _, voice, _ = app_context
    voice.recognize_speech.return_value = "add 1 salmon"
    app.controller = MagicMock()
    # Mimic real behaviour: process_command would call update_display_with_inventory.
    def fake_process(cmd):
        app.controller.update_display_with_inventory()
        return True, "salmon now has 1 in inventory."
    app.controller.process_command.side_effect = fake_process
    app.running = True

    app._handle_voice_command()

    assert app.controller.update_display_with_inventory.call_count == 1


def test_orphaned_voice_task_does_not_emit_audio(app_context):
    """A task whose manager has been retired must not call output_*."""
    app, _, _, _, _, _, voice, audio = app_context
    app.running = True
    app.controller = MagicMock()
    voice.recognize_speech.return_value = "add 1 salmon"

    # Simulate retire: bound manager no longer matches the owned one.
    orphan_manager = MagicMock()
    orphan_manager.recognize_speech.return_value = "add 1 salmon"

    app._handle_voice_command(voice_manager=orphan_manager)

    audio.output_confirmation.assert_not_called()
    audio.output_error.assert_not_called()
    app.controller.process_command.assert_not_called()


def test_refresh_display_best_effort_does_not_raise(app_context):
    app, _, _, _, _, _, _, _ = app_context
    app.controller = MagicMock()
    app.controller.update_display_with_inventory.side_effect = RuntimeError("display offline")

    app._refresh_display_best_effort()

    app.controller.update_display_with_inventory.assert_called_once()


def test_run_processes_motion_transition_and_cleans_up(app_context):
    app, _, _, _, _, motion, _, _ = app_context
    motion.detect_motion.return_value = True

    def stop_after_voice(*_args, **_kwargs):
        app.running = False
        app.shutdown_event.set()

    app._kick_voice_command = MagicMock(side_effect=stop_after_voice)

    with patch('pi_inventory_system.main.run_startup_diagnostics',
               return_value=(False, True, False, None)):
        app.run()

    # Kicked on the motion transition, and possibly again by the
    # continuous-listening window within the same iteration.
    app._kick_voice_command.assert_called_with()
    assert app._kick_voice_command.call_count >= 1
    motion.cleanup.assert_called()


def test_run_retries_motion_after_failed_diagnostics(app_context):
    app, _, _, _, _, motion, _, _ = app_context
    motion.is_supported.return_value = True
    motion.detect_motion.return_value = True

    def stop_after_voice(*_args, **_kwargs):
        app.running = False
        app.shutdown_event.set()

    app._kick_voice_command = MagicMock(side_effect=stop_after_voice)

    with patch('pi_inventory_system.main.run_startup_diagnostics',
               return_value=(False, False, False, None)):
        app.run()

    motion.is_supported.assert_called()
    app._kick_voice_command.assert_called_with()
    assert app._kick_voice_command.call_count >= 1


def test_run_auto_mode_uses_voice_when_motion_is_unavailable(app_context):
    app, _, _, _, _, motion, _, _ = app_context
    motion.is_supported.return_value = False

    def stop_after_voice(*_args, **_kwargs):
        app.running = False
        app.shutdown_event.set()

    app._kick_voice_command = MagicMock(side_effect=stop_after_voice)

    with patch('pi_inventory_system.main.run_startup_diagnostics',
               return_value=(False, False, False, None)):
        app.run()

    app._kick_voice_command.assert_called_once_with()


def test_cleanup_continues_after_resource_failure(app_context):
    app, _, db, _, _, motion, voice, audio = app_context
    motion.cleanup.side_effect = RuntimeError("gpio busy")

    app._cleanup()

    motion.cleanup.assert_called()
    voice.cleanup.assert_called()
    audio.cleanup.assert_called()
    db.cleanup.assert_called()


def test_initialize_returns_false_on_diagnostics_exception(app_context):
    app, _, _, _, _, _, _, _ = app_context

    with patch('pi_inventory_system.main.run_startup_diagnostics',
               side_effect=RuntimeError("SPI exploded")):
        assert app.initialize() is False


def test_run_cleans_up_when_initialize_raises(app_context):
    """A diagnostics crash during startup must still run _cleanup so GPIO,
    audio worker and DB are released."""
    app, _, db, _, _, motion, _, audio = app_context

    with patch('pi_inventory_system.main.run_startup_diagnostics',
               side_effect=RuntimeError("SPI exploded")):
        app.run()

    motion.cleanup.assert_called()
    audio.cleanup.assert_called()
    db.cleanup.assert_called()


def test_initialize_does_not_replay_startup_chime(app_context):
    """Diagnostics already played the success sound as its audio probe;
    initialize must not chime a second time seconds later."""
    app, _, _, _, _, _, _, audio = app_context

    with patch('pi_inventory_system.main.run_startup_diagnostics',
               return_value=(True, True, True, MagicMock())):
        assert app.initialize() is True

    audio.play_sound.assert_not_called()
    audio.reset_circuit_breakers.assert_called_once()
