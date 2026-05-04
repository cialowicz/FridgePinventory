"""FridgePinventory entry point — orchestration only, no business logic."""

import logging
import os
import signal
import threading
import time
import traceback
from typing import Optional

from .audio_feedback_manager import AudioFeedbackManager
from .config_manager import create_config_manager
from .constants import (
    ACTIVATION_ALWAYS_LISTEN,
    ACTIVATION_AUTO,
    ACTIVATION_MANUAL,
    ACTIVATION_MOTION,
    ACTIVATION_SIMULATION,
    VALID_ACTIVATION_MODES,
)
from .database_manager import create_database_manager
from .diagnostics import run_startup_diagnostics
from .display_manager import cleanup_display, initialize_display
from .inventory_controller import InventoryController
from .motion_loop import ACTIVE, IDLE, MotionLoop
from .motion_sensor_manager import MotionSensorManager
from .voice_recognition_manager import VoiceRecognitionManager


VOICE_TIMEOUT_SECONDS = 15
MAX_ORPHANED_VOICE_TASKS = 2


class _VoiceTask:
    """Small daemon-thread task wrapper for voice recognition work.

    ThreadPoolExecutor uses non-daemon workers that Python joins at process
    shutdown. That is the wrong failure mode for microphone APIs that may hang,
    so voice work runs in an app-owned daemon thread that can be orphaned after
    timeout without blocking process exit.
    """

    def __init__(self, target, *args):
        self._done = threading.Event()
        self._exception: Optional[BaseException] = None
        self._result = None
        self._thread = threading.Thread(
            target=self._run,
            args=(target, args),
            name="voice-command",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def _run(self, target, args) -> None:
        try:
            self._result = target(*args)
        except BaseException as e:
            self._exception = e
        finally:
            self._done.set()

    def done(self) -> bool:
        return self._done.is_set()

    def result(self, timeout: Optional[float] = None):
        if not self._done.wait(timeout):
            raise TimeoutError("voice task did not finish")
        if self._exception:
            raise self._exception
        return self._result


class FridgePinventoryApp:
    """Main application orchestrator."""

    def __init__(self, config_path: Optional[str] = None, db_path: Optional[str] = None):
        self.config_manager = create_config_manager(config_path)
        self.db_manager = create_database_manager(self.config_manager, db_path=db_path)

        self._setup_logging()
        self.logger = logging.getLogger(__name__)

        self.controller: Optional[InventoryController] = None
        self.display = None
        self.hardware_status: Optional[tuple] = None

        self.motion_manager = MotionSensorManager(config_manager=self.config_manager)
        self.voice_manager = VoiceRecognitionManager(config_manager=self.config_manager)
        self.audio_feedback = AudioFeedbackManager(config_manager=self.config_manager)

        self.running = False
        self.shutdown_event = threading.Event()

        self._voice_future: Optional[_VoiceTask] = None
        self._voice_started_at: Optional[float] = None
        self._voice_timeout_logged = False
        self._orphaned_voice_tasks: list[_VoiceTask] = []
        self._orphaned_voice_managers: list[tuple[_VoiceTask, VoiceRecognitionManager]] = []
        self._voice_disabled = False
        # Bound copies of the manager triple submitted with each voice task —
        # protects an in-flight task from a mid-flight reset_voice_worker swap.
        self._owned_voice_manager = self.voice_manager

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.logger.info(
            "Application starting. "
            f"User: {os.getenv('USER', 'N/A')}, Home: {os.getenv('HOME', 'N/A')}"
        )

    def _setup_logging(self) -> None:
        system_config = self.config_manager.get_system_config()
        log_level = getattr(logging, system_config.get('log_level', 'INFO').upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format=(
                '%(asctime)s - %(name)s - %(levelname)s - '
                '[%(pathname)s:%(lineno)d] - %(message)s'
            ),
            handlers=[logging.StreamHandler()],
        )

    def initialize(self) -> bool:
        self.logger.info("Starting FridgePinventory initialization...")
        display_ok, motion_ok, audio_ok, display_instance = run_startup_diagnostics(
            self.config_manager,
            motion_manager=self.motion_manager,
            audio_manager=self.audio_feedback,
        )
        self.hardware_status = (display_ok, motion_ok, audio_ok)
        self.display = display_instance
        if not self.display and display_ok:
            self.logger.warning("Display reported OK but no instance returned, retrying init")
            self.display = initialize_display(self.config_manager)

        self.controller = InventoryController(self.db_manager, self.display, self.config_manager)

        if audio_ok:
            self.audio_feedback.play_sound('success')
        # Diagnostics may have tripped a transient failure or two during the
        # WAV smoke-test; re-enable both breakers so runtime feedback is heard.
        self.audio_feedback.reset_circuit_breakers()
        self.logger.info("FridgePinventory initialization complete")
        return True

    def _refresh_display_best_effort(self) -> None:
        if not self.controller:
            return
        try:
            self.controller.update_display_with_inventory()
        except Exception as e:
            self.logger.error(f"Display refresh failed: {e}")

    def _motion_sensor_available(self) -> bool:
        try:
            is_available = getattr(self.motion_manager, 'is_available', None)
            if callable(is_available):
                available = is_available()
                if isinstance(available, bool):
                    return available
            return bool(self.motion_manager.is_supported())
        except Exception as e:
            self.logger.error(f"Motion sensor support check failed: {e}")
            return False

    def _activation_mode(self) -> str:
        system_config = self.config_manager.get_system_config()
        mode = str(system_config.get('activation_mode', ACTIVATION_AUTO)).lower()
        if mode not in VALID_ACTIVATION_MODES:
            self.logger.warning(f"Invalid activation_mode={mode}; falling back to auto")
            return ACTIVATION_AUTO
        return mode

    def _simulation_voice_interval(self) -> float:
        system_config = self.config_manager.get_system_config()
        interval = system_config.get('simulation_voice_interval', 5.0)
        if not isinstance(interval, (int, float)) or interval <= 0:
            return 5.0
        return float(interval)

    def _build_motion_loop(self) -> MotionLoop:
        system_config = self.config_manager.get_system_config()
        return MotionLoop(
            motion_check_interval=system_config.get('motion_check_interval', 0.5),
            idle_delay=system_config.get('idle_delay', 1.0),
            active_delay=system_config.get('main_loop_delay', 0.1),
        )

    def _signal_handler(self, signum, _frame):
        self.logger.info(f"Received signal {signum}, initiating shutdown...")
        self.running = False
        self.shutdown_event.set()

    def _handle_voice_command(self, voice_manager=None) -> None:
        # voice_manager is captured at submit time so a later reset_voice_worker
        # swap cannot redirect this in-flight task onto a different manager.
        voice_manager = voice_manager or self.voice_manager
        try:
            command = voice_manager.recognize_speech()
            # If we were retired by a timeout, drop on the floor instead of
            # firing audio cues seconds after the user moved on.
            if voice_manager is not self._owned_voice_manager or not self.running:
                return
            if command:
                self.logger.info(f"Command received: {command}")
                success, feedback = self.controller.process_command(command)
                self.logger.info(f"Command result: {feedback}")
                if success:
                    # Speak the confirmation, but choose the chime based on the
                    # resulting state: removed-from-inventory uses the warning
                    # tone so users distinguish "added/updated" from "now empty".
                    spoken = feedback or "Command executed successfully."
                    if feedback and "removed from inventory" in feedback:
                        self.audio_feedback.speak(spoken)
                        self.audio_feedback.play_sound('warning')
                    else:
                        self.audio_feedback.output_confirmation(spoken)
                else:
                    self.audio_feedback.output_error(feedback or "Command failed.")
        except Exception as e:
            self.logger.error(f"Error handling voice command: {e}")
            if voice_manager is not self._owned_voice_manager or not self.running:
                return
            try:
                self.audio_feedback.output_error("Voice command failed. Please try again.")
            except Exception as feedback_error:
                self.logger.error(f"Failed to output voice error feedback: {feedback_error}")

    def _check_voice_future(self) -> bool:
        """Return True when a voice task is still running."""
        if self._voice_future is None:
            return False

        if self._voice_future.done():
            try:
                self._voice_future.result()
            except Exception as e:
                self.logger.error(f"Voice command task failed: {e}")
            finally:
                self._voice_future = None
                self._voice_started_at = None
                self._voice_timeout_logged = False
            return False

        if self._voice_started_at is not None:
            elapsed = time.monotonic() - self._voice_started_at
            if elapsed > VOICE_TIMEOUT_SECONDS and not self._voice_timeout_logged:
                self.logger.warning("Voice command timed out")
                self._voice_timeout_logged = True
                self._reset_voice_worker()
                return False
        return True

    def _reset_voice_worker(self) -> None:
        """Retire a stuck voice worker so subsequent commands can run.

        The blocked task likely holds the microphone open inside
        ``recognizer.listen``. Python cannot kill that thread, so the in-flight
        daemon task is orphaned from this app instance; `_handle_voice_command` checks
        ``voice_manager is self._owned_voice_manager`` and bails out instead
        of firing audio cues from beyond the grave. We cap live orphaned tasks
        so repeated backend hangs disable voice instead of spawning forever.
        """
        future = self._voice_future
        old_manager = self.voice_manager
        self._owned_voice_manager = None
        if future and not future.done():
            self._orphaned_voice_tasks.append(future)
            self._orphaned_voice_managers.append((future, old_manager))
        else:
            self._cleanup_voice_manager_best_effort(old_manager, "Old voice manager")

        self._voice_future = None
        self._voice_started_at = None
        self._voice_timeout_logged = False
        self._prune_orphaned_voice_tasks()
        if len(self._orphaned_voice_tasks) >= MAX_ORPHANED_VOICE_TASKS:
            self._voice_disabled = True
            self._owned_voice_manager = None
            self.logger.error("Voice input disabled after repeated recognition timeouts")
            return

        self.voice_manager = VoiceRecognitionManager(config_manager=self.config_manager)
        self._owned_voice_manager = self.voice_manager
        self._voice_disabled = False

    def _wait_for_voice_worker(self, timeout: float = 8.0) -> bool:
        """Block briefly until the active voice future has finished so cleanup
        does not yank the DB / TTS engine out from under it."""
        future = self._voice_future
        if future is None:
            return True
        try:
            future.result(timeout=timeout)
        except TimeoutError:
            self.logger.warning("Voice worker did not finish before cleanup timeout")
            return False
        except Exception as e:
            self.logger.warning(f"Voice worker exited with error: {e}")
        return True

    def _cleanup_voice_manager_best_effort(self, manager, label: str = "Voice manager") -> None:
        try:
            manager.cleanup()
        except Exception as e:
            self.logger.warning(f"{label} cleanup failed: {e}")

    def _cleanup_active_voice_manager(self) -> None:
        if self._voice_future and not self._voice_future.done():
            self.logger.warning(
                "Skipping voice manager cleanup while voice worker is still running"
            )
            return
        self._cleanup_voice_manager_best_effort(self.voice_manager)

    def _prune_orphaned_voice_tasks(self) -> None:
        remaining_managers = []
        for task, manager in self._orphaned_voice_managers:
            if task.done():
                self._cleanup_voice_manager_best_effort(manager, "Retired voice manager")
            else:
                remaining_managers.append((task, manager))
        self._orphaned_voice_managers = remaining_managers
        self._orphaned_voice_tasks = [
            task for task in self._orphaned_voice_tasks if not task.done()
        ]

    def _restore_voice_worker_if_available(self) -> None:
        if not self._voice_disabled:
            return
        self._prune_orphaned_voice_tasks()
        if len(self._orphaned_voice_tasks) >= MAX_ORPHANED_VOICE_TASKS:
            return
        self.voice_manager = VoiceRecognitionManager(config_manager=self.config_manager)
        self._owned_voice_manager = self.voice_manager
        self._voice_disabled = False
        self.logger.info("Voice input re-enabled after orphaned task completed")

    def _kick_voice_command(self) -> None:
        self._restore_voice_worker_if_available()
        if self._voice_disabled:
            self.logger.warning("Voice input disabled; skipping voice command")
            return
        if self._check_voice_future():
            return
        self._voice_started_at = time.monotonic()
        bound_manager = self.voice_manager
        self._voice_future = _VoiceTask(self._handle_voice_command, bound_manager)
        self._voice_future.start()

    def _run_without_motion(
        self,
        activation_mode: str,
        next_voice_at: float,
    ) -> tuple[bool, float]:
        """Handle one loop iteration when motion hardware is unavailable.

        Returns (continue_without_motion, next_voice_at). If continue_without_motion
        is False, the caller should resume normal motion polling.
        """
        if activation_mode == ACTIVATION_MOTION:
            self.shutdown_event.wait(timeout=1.0)
            return True, next_voice_at
        if activation_mode == ACTIVATION_MANUAL:
            self.logger.debug("Manual activation mode selected; waiting")
            self.shutdown_event.wait(timeout=1.0)
            return True, next_voice_at

        now = time.time()
        interval = self._simulation_voice_interval()
        if now >= next_voice_at:
            self.logger.info("Motion unavailable; attempting voice activation")
            self._kick_voice_command()
            next_voice_at = now + interval
        sleep_for = max(0.1, min(1.0, next_voice_at - now))
        self.shutdown_event.wait(timeout=sleep_for)
        return True, next_voice_at

    def _handle_motion_decision(self, loop, decision, display_ok: bool, previous_mode: str) -> str:
        if decision.enter_idle:
            self.logger.info("Entering idle mode")
        if decision.new_motion:
            self.logger.info("Motion detected, transitioning to active mode")
            if display_ok:
                self._refresh_display_best_effort()
            self._kick_voice_command()

        if previous_mode == ACTIVE and loop.mode != ACTIVE:
            self.logger.info("Motion ended, deactivating")
        return loop.mode

    def run(self) -> None:
        if not self.initialize():
            self.logger.error("Failed to initialize application")
            return

        display_ok, motion_ok, _ = self.hardware_status
        self.running = True

        try:
            if display_ok:
                self._refresh_display_best_effort()

            loop = self._build_motion_loop()

            previous_mode = loop.mode
            motion_available = motion_ok
            motion_retry_announced = False
            next_voice_at = 0.0
            activation_mode = self._activation_mode()
            if not motion_available:
                self.logger.warning(
                    "Motion sensor unavailable at startup; will retry until it returns"
                )
                motion_retry_announced = True
            while self.running and not self.shutdown_event.is_set():
                self._check_voice_future()
                activation_mode = self._activation_mode()

                if activation_mode == ACTIVATION_MANUAL:
                    self.shutdown_event.wait(timeout=1.0)
                    continue
                if activation_mode in (ACTIVATION_ALWAYS_LISTEN, ACTIVATION_SIMULATION):
                    _, next_voice_at = self._run_without_motion(activation_mode, next_voice_at)
                    continue

                if not motion_available:
                    motion_available = self._motion_sensor_available()
                    if motion_available:
                        self.logger.info("Motion sensor recovered; resuming motion polling")
                        motion_retry_announced = False
                    else:
                        if not motion_retry_announced:
                            self.logger.warning("Motion sensor unavailable; will retry")
                            motion_retry_announced = True
                        _, next_voice_at = self._run_without_motion(
                            activation_mode,
                            next_voice_at,
                        )
                        continue

                decision = loop.step(time.time(), self.motion_manager.detect_motion)
                if (
                    hasattr(self.motion_manager, 'is_healthy')
                    and not self.motion_manager.is_healthy()
                ):
                    motion_available = False
                    self.logger.warning("Motion sensor became unhealthy; entering recovery")
                previous_mode = self._handle_motion_decision(
                    loop,
                    decision,
                    display_ok,
                    previous_mode,
                )

                if loop.mode == IDLE:
                    self.shutdown_event.wait(timeout=decision.sleep_seconds)
                else:
                    time.sleep(decision.sleep_seconds)
        except Exception as e:
            self.logger.error(f"Unexpected error in main loop: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        self.logger.info("Shutting down...")
        self.running = False

        cleanup_steps = [
            ("motion manager", self.motion_manager.cleanup),
            # Wait for any in-flight voice worker to finish *before* tearing
            # down the DB / audio. Otherwise process_command running on the
            # worker thread can be writing to a connection the main thread
            # just closed, or calling output_confirmation on a stopped TTS
            # engine. The voice manager's mic timeout caps how long this
            # blocks; we add a generous ceiling on top of that.
            ("voice worker", self._wait_for_voice_worker),
            ("voice manager", self._cleanup_active_voice_manager),
            ("retired voice managers", self._prune_orphaned_voice_tasks),
            ("audio feedback", self.audio_feedback.cleanup),
        ]
        if self.display:
            cleanup_steps.append(
                ("display", lambda: cleanup_display(self.display, self.config_manager))
            )
        if hasattr(self.db_manager, 'cleanup'):
            cleanup_steps.append(("database", self.db_manager.cleanup))

        for label, cleanup_fn in cleanup_steps:
            try:
                cleanup_fn()
            except Exception as e:
                self.logger.error(f"Error during {label} cleanup: {e}")

        self.logger.info("Cleanup complete")


def main():
    FridgePinventoryApp().run()


if __name__ == "__main__":
    main()
