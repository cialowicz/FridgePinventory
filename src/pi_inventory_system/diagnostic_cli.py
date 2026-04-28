"""Hardware self-test CLI.

Replaces the old full_hardware_diagnostic.py — instead of re-implementing
detection logic, this exercises the real production managers and reports
their status. Run with::

    fridge-diagnostic
    # or
    python -m pi_inventory_system.diagnostic_cli
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Callable, List, Tuple

from .audio_feedback_manager import AudioFeedbackManager
from .config_manager import create_config_manager
from .display_manager import display_text, initialize_display, is_display_supported
from .motion_sensor_manager import MotionSensorManager
from .platform_info import is_raspberry_pi, is_raspberry_pi_5
from .voice_recognition_manager import VoiceRecognitionManager

logger = logging.getLogger(__name__)


def _check(label: str, fn: Callable[[], bool]) -> Tuple[str, bool, str]:
    """Run fn(); capture (label, ok, detail)."""
    try:
        ok = bool(fn())
        return (label, ok, "")
    except Exception as e:
        return (label, False, f"{type(e).__name__}: {e}")


def _check_spi() -> bool:
    return any(os.path.exists(d) for d in ("/dev/spidev0.0", "/dev/spidev0.1"))


def _check_i2c() -> bool:
    return any(os.path.exists(f"/dev/i2c-{i}") for i in range(3))


def _check_aplay() -> bool:
    return subprocess.run(
        ["aplay", "-l"], capture_output=True, text=True, check=False
    ).returncode == 0


def _check_arecord() -> bool:
    return subprocess.run(
        ["arecord", "-l"], capture_output=True, text=True, check=False
    ).returncode == 0


def _platform_summary() -> List[Tuple[str, bool, str]]:
    return [
        ("Running on a Raspberry Pi", is_raspberry_pi(), ""),
        ("Raspberry Pi 5 detected", is_raspberry_pi_5(), ""),
        _check("SPI device present", _check_spi),
        _check("I2C device present", _check_i2c),
        _check("aplay available (ALSA playback)", _check_aplay),
        _check("arecord available (ALSA capture)", _check_arecord),
    ]


def _display_summary(config_manager) -> List[Tuple[str, bool, str]]:
    rows: List[Tuple[str, bool, str]] = []
    rows.append(("Display configured & supported",
                 is_display_supported(config_manager), ""))
    display = initialize_display(config_manager)
    if display is None:
        rows.append(("Display initialised", False, "WaveshareDisplay returned None"))
        return rows
    rows.append(("Display initialised", True, f"{display.WIDTH}x{display.HEIGHT}"))
    try:
        rendered = display_text(display, "Diagnostic\nself-test",
                                config_manager=config_manager)
        rows.append(("Display rendered text", bool(rendered), ""))
    finally:
        try:
            display.cleanup()
        except Exception as e:
            logger.warning(f"Display cleanup failed: {e}")
    return rows


def _motion_summary(config_manager) -> List[Tuple[str, bool, str]]:
    manager = MotionSensorManager(config_manager=config_manager)
    rows: List[Tuple[str, bool, str]] = []
    rows.append(("Motion sensor supported", manager.is_supported(), ""))
    if not manager.is_supported():
        return rows
    try:
        readings = [manager.detect_motion() for _ in range(3)]
        rows.append(("Motion sensor reads",
                     manager.is_healthy(),
                     f"readings={readings}"))
    finally:
        try:
            manager.cleanup()
        except Exception as e:
            logger.warning(f"Motion cleanup failed: {e}")
    return rows


def _audio_summary(config_manager) -> List[Tuple[str, bool, str]]:
    manager = AudioFeedbackManager(config_manager=config_manager)
    rows: List[Tuple[str, bool, str]] = []
    try:
        rows.append(("Audio playback (success.wav)",
                     manager.play_sound("success"), ""))
    finally:
        try:
            manager.cleanup()
        except Exception as e:
            logger.warning(f"Audio cleanup failed: {e}")
    return rows


def _voice_summary(config_manager) -> List[Tuple[str, bool, str]]:
    manager = VoiceRecognitionManager(config_manager=config_manager)
    rows: List[Tuple[str, bool, str]] = []
    try:
        rows.append(("Voice recogniser initialises", manager.initialize(), ""))
    finally:
        try:
            manager.cleanup()
        except Exception as e:
            logger.warning(f"Voice cleanup failed: {e}")
    return rows


def _print_section(title: str, rows: List[Tuple[str, bool, str]]) -> bool:
    print(f"\n=== {title} ===")
    section_ok = True
    for label, ok, detail in rows:
        status = "OK  " if ok else "FAIL"
        suffix = f"  ({detail})" if detail else ""
        print(f"  [{status}] {label}{suffix}")
        section_ok = section_ok and ok
    return section_ok


def run_diagnostic(config_manager=None) -> int:
    """Run the full diagnostic. Returns 0 on overall pass, 1 otherwise."""
    if config_manager is None:
        config_manager = create_config_manager()

    sections = (
        ("Platform", _platform_summary()),
        ("Display", _display_summary(config_manager)),
        ("Motion sensor", _motion_summary(config_manager)),
        ("Audio playback", _audio_summary(config_manager)),
        ("Voice recogniser", _voice_summary(config_manager)),
    )
    overall_ok = True
    for title, rows in sections:
        overall_ok = _print_section(title, rows) and overall_ok

    print()
    print("Overall:", "OK" if overall_ok else "FAIL")
    return 0 if overall_ok else 1


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return run_diagnostic()


if __name__ == "__main__":
    sys.exit(main())
