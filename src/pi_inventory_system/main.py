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
        self._retired_voice_executors = []
        self._retired_voice_managers = []

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

    def _handle_voice_command(self, display_ok: bool) -> None:
        try:
            command = self.voice_manager.recognize_speech()
            if command and self.running:
                self.logger.info(f"Command received: {command}")
                success, feedback = self.controller.process_command(command)
                self.logger.info(f"Command result: {feedback}")
                if success:
                    self.audio_feedback.output_confirmation(
                        feedback or "Command executed successfully."
                    )
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
        """Retire the current voice worker after a timeout and allow future commands."""
        if self._voice_future:
            self._voice_future.cancel()
        self._retired_voice_executors.append(self._voice_executor)
        self._retired_voice_managers.append(self.voice_manager)
        self._voice_executor.shutdown(wait=False, cancel_futures=True)
        self.voice_manager = VoiceRecognitionManager(config_manager=self.config_manager)
        self._voice_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice")
        self._voice_future = None
        self._voice_started_at = None
        self._voice_timeout_logged = False

    def _kick_voice_command(self, display_ok: bool) -> None:
        if self._check_voice_future():
            return
        self._voice_started_at = time.monotonic()
        self._voice_future = self._voice_executor.submit(self._handle_voice_command, display_ok)

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
            motion_retry_logged = False
            while self.running and not self.shutdown_event.is_set():
                self._check_voice_future()

                if not motion_available:
                    motion_available = self._motion_sensor_available()
                    if motion_available and not motion_retry_logged:
                        self.logger.warning("Motion diagnostics failed; retrying motion polling")
                        motion_retry_logged = True

                if not motion_available:
                    self.shutdown_event.wait(timeout=1.0)
                    continue

                decision = loop.step(time.time(), self.motion_manager.detect_motion)

                if decision.enter_idle:
                    self.logger.info("Entering idle mode")
                if decision.new_motion:
                    self.logger.info("Motion detected, transitioning to active mode")
                    if display_ok:
                        self._refresh_display_best_effort()
                    self._kick_voice_command(display_ok)

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
            ("retired voice executors", self._cleanup_retired_voice_executors),
            ("motion manager", self.motion_manager.cleanup),
            ("voice manager", self.voice_manager.cleanup),
            ("retired voice managers", self._cleanup_retired_voice_managers),
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

    def _cleanup_retired_voice_executors(self) -> None:
        for executor in self._retired_voice_executors:
            executor.shutdown(wait=False, cancel_futures=True)
        self._retired_voice_executors = []

    def _cleanup_retired_voice_managers(self) -> None:
        for manager in self._retired_voice_managers:
            manager.cleanup()
        self._retired_voice_managers = []


def main():
    FridgePinventoryApp().run()


if __name__ == "__main__":
    main()
