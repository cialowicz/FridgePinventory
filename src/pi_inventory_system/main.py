"""FridgePinventory entry point — orchestration only, no business logic."""

import logging
import os
import signal
import threading
import time
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Optional

from .audio_feedback_manager import AudioFeedbackManager
from .config_manager import create_config_manager
from .database_manager import create_database_manager
from .diagnostics import run_startup_diagnostics
from .display_manager import cleanup_display, initialize_display
from .inventory_controller import InventoryController
from .motion_loop import ACTIVE, IDLE, MotionLoop
from .motion_sensor_manager import MotionSensorManager
from .voice_recognition_manager import VoiceRecognitionManager


VOICE_TIMEOUT_SECONDS = 15


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

        self._voice_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice")
        self._voice_future: Optional[Future] = None
        self._voice_started_at: Optional[float] = None
        self._voice_timeout_logged = False
        # Bound copies of the manager triple submitted with each voice task —
        # protects an in-flight task from a mid-flight reset_voice_worker swap.
        self._owned_voice_manager = self.voice_manager

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.logger.info(
            f"Application starting. User: {os.getenv('USER', 'N/A')}, Home: {os.getenv('HOME', 'N/A')}")

    def _setup_logging(self) -> None:
        system_config = self.config_manager.get_system_config()
        log_level = getattr(logging, system_config.get('log_level', 'INFO').upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - [%(pathname)s:%(lineno)d] - %(message)s',
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
            return self.motion_manager.is_supported()
        except Exception as e:
            self.logger.error(f"Motion sensor support check failed: {e}")
            return False

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
        ``recognizer.listen``; we shut down the old executor (no wait, since
        joining would block forever) and best-effort the old manager's cleanup
        before swapping in fresh ones. The in-flight task is now orphaned
        from this app instance — `_handle_voice_command` checks
        ``voice_manager is self._owned_voice_manager`` and bails out instead
        of firing audio cues from beyond the grave.
        """
        if self._voice_future:
            self._voice_future.cancel()
        old_executor = self._voice_executor
        old_manager = self.voice_manager
        old_executor.shutdown(wait=False, cancel_futures=True)
        try:
            old_manager.cleanup()
        except Exception as e:
            self.logger.warning(f"Old voice manager cleanup failed: {e}")

        self.voice_manager = VoiceRecognitionManager(config_manager=self.config_manager)
        self._owned_voice_manager = self.voice_manager
        self._voice_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice")
        self._voice_future = None
        self._voice_started_at = None
        self._voice_timeout_logged = False

    def _kick_voice_command(self) -> None:
        if self._check_voice_future():
            return
        self._voice_started_at = time.monotonic()
        bound_manager = self.voice_manager
        self._voice_future = self._voice_executor.submit(
            self._handle_voice_command, bound_manager,
        )

    def run(self) -> None:
        if not self.initialize():
            self.logger.error("Failed to initialize application")
            return

        display_ok, motion_ok, _ = self.hardware_status
        self.running = True

        try:
            if display_ok:
                self._refresh_display_best_effort()

            system_config = self.config_manager.get_system_config()
            loop = MotionLoop(
                motion_check_interval=system_config.get('motion_check_interval', 0.5),
                idle_delay=system_config.get('idle_delay', 1.0),
                active_delay=system_config.get('main_loop_delay', 0.1),
            )

            previous_mode = loop.mode
            motion_available = motion_ok
            motion_retry_announced = False
            if not motion_available:
                self.logger.warning("Motion sensor unavailable at startup; will retry until it returns")
                motion_retry_announced = True
            while self.running and not self.shutdown_event.is_set():
                self._check_voice_future()

                if not motion_available:
                    motion_available = self._motion_sensor_available()
                    if motion_available:
                        self.logger.info("Motion sensor recovered; resuming motion polling")
                        motion_retry_announced = False
                    else:
                        if not motion_retry_announced:
                            self.logger.warning("Motion sensor unavailable; will retry")
                            motion_retry_announced = True
                        self.shutdown_event.wait(timeout=1.0)
                        continue

                decision = loop.step(time.time(), self.motion_manager.detect_motion)

                if decision.enter_idle:
                    self.logger.info("Entering idle mode")
                if decision.new_motion:
                    self.logger.info("Motion detected, transitioning to active mode")
                    if display_ok:
                        self._refresh_display_best_effort()
                    self._kick_voice_command()

                if previous_mode == ACTIVE and loop.mode != ACTIVE:
                    self.logger.info("Motion ended, deactivating")
                previous_mode = loop.mode

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
            ("voice executor", lambda: self._voice_executor.shutdown(wait=False, cancel_futures=True)),
            ("motion manager", self.motion_manager.cleanup),
            ("voice manager", self.voice_manager.cleanup),
            ("audio feedback", self.audio_feedback.cleanup),
        ]
        if self.display:
            cleanup_steps.append(("display", lambda: cleanup_display(self.display)))
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
