"""FridgePinventory entry point — orchestration only, no business logic."""

import logging
import os
import signal
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional

from .audio_feedback_manager import AudioFeedbackManager
from .config_manager import get_default_config_manager
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
        self.config_manager = get_default_config_manager()
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
        display_ok, motion_ok, audio_ok, display_instance = run_startup_diagnostics(self.config_manager)
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

    def _signal_handler(self, signum, _frame):
        self.logger.info(f"Received signal {signum}, initiating shutdown...")
        self.running = False
        self.shutdown_event.set()

    def _handle_voice_command(self, display_ok: bool) -> None:
        try:
            command = self.voice_manager.recognize_speech()
            if command and self.running:
                self.logger.info(f"Command received: {command}")
                _, feedback = self.controller.process_command(command)
                self.logger.info(f"Command result: {feedback}")
                if display_ok:
                    self.controller.update_display_with_inventory()
        except Exception as e:
            self.logger.error(f"Error handling voice command: {e}")

    def _kick_voice_command(self, display_ok: bool) -> None:
        future = self._voice_executor.submit(self._handle_voice_command, display_ok)
        try:
            future.result(timeout=VOICE_TIMEOUT_SECONDS)
        except FuturesTimeoutError:
            self.logger.warning("Voice command timed out")
            future.cancel()

    def run(self) -> None:
        if not self.initialize():
            self.logger.error("Failed to initialize application")
            return

        display_ok, motion_ok, _ = self.hardware_status
        self.running = True

        try:
            if display_ok:
                self.controller.update_display_with_inventory()

            system_config = self.config_manager.get_system_config()
            loop = MotionLoop(
                motion_check_interval=system_config.get('motion_check_interval', 0.5),
                idle_delay=system_config.get('idle_delay', 1.0),
                active_delay=system_config.get('main_loop_delay', 0.1),
            )

            previous_mode = loop.mode
            while self.running and not self.shutdown_event.is_set():
                if not motion_ok:
                    self.shutdown_event.wait(timeout=1.0)
                    continue

                decision = loop.step(time.time(), self.motion_manager.detect_motion)

                if decision.enter_idle:
                    self.logger.info("Entering idle mode")
                if decision.new_motion:
                    self.logger.info("Motion detected, transitioning to active mode")
                    if display_ok:
                        self.controller.update_display_with_inventory()
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
        try:
            self._voice_executor.shutdown(wait=False, cancel_futures=True)
            self.motion_manager.cleanup()
            self.voice_manager.cleanup()
            self.audio_feedback.cleanup()
            if self.display:
                cleanup_display(self.display)
            if hasattr(self.db_manager, 'cleanup'):
                self.db_manager.cleanup()
            self.logger.info("Cleanup complete")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


def main():
    FridgePinventoryApp().run()


if __name__ == "__main__":
    main()
