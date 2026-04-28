"""Tests for the diagnostics module."""

import pytest
from unittest.mock import MagicMock, call, patch

from pi_inventory_system.diagnostics import run_startup_diagnostics


@pytest.fixture
def mock_display_init():
    with patch('pi_inventory_system.diagnostics.initialize_display') as init:
        display = MagicMock()
        init.return_value = display
        yield display


@pytest.fixture
def mock_motion_manager():
    with patch('pi_inventory_system.diagnostics.MotionSensorManager') as manager_class:
        manager = MagicMock()
        manager.is_supported.return_value = True
        manager.detect_motion.return_value = False
        manager_class.return_value = manager
        yield manager


@pytest.fixture
def mock_supported():
    with patch('pi_inventory_system.diagnostics.is_display_supported', return_value=True) as m:
        yield m


@pytest.fixture
def mock_audio():
    with patch('pi_inventory_system.diagnostics.AudioFeedbackManager') as manager_class:
        manager = MagicMock()
        manager.play_sound.return_value = True
        manager_class.return_value = manager
        yield manager


@pytest.fixture
def cfg():
    return MagicMock()


def test_diagnostics_display_success(mock_display_init, mock_motion_manager, mock_supported, mock_audio, cfg):
    with patch('pi_inventory_system.diagnostics.display_text', return_value=True) as mock_text:
        display_ok, motion_ok, audio_ok, _ = run_startup_diagnostics(cfg)
        assert (display_ok, motion_ok, audio_ok) == (True, True, True)
        mock_text.assert_has_calls([
            call(mock_display_init, "FridgePinventory\nstarting up...", config_manager=cfg),
            call(mock_display_init, "Diagnostics complete:\nDisplay: OK\nMotion: OK\nAudio: OK", config_manager=cfg),
        ], any_order=False)


def test_diagnostics_display_failure(mock_display_init, mock_motion_manager, mock_supported, mock_audio, cfg):
    with patch('pi_inventory_system.diagnostics.display_text', return_value=False):
        display_ok, motion_ok, audio_ok, _ = run_startup_diagnostics(cfg)
        assert display_ok is False
        assert motion_ok is True
        assert audio_ok is True


def test_diagnostics_motion_sensor_failure(mock_display_init, mock_motion_manager, mock_supported, mock_audio, cfg):
    mock_motion_manager.detect_motion.side_effect = Exception("sensor explosion")
    with patch('pi_inventory_system.diagnostics.display_text', return_value=True):
        _, motion_ok, _, _ = run_startup_diagnostics(cfg)
        assert motion_ok is False


def test_diagnostics_platform_not_supported(mock_audio, cfg):
    with patch('pi_inventory_system.diagnostics.is_display_supported', return_value=False), \
         patch('pi_inventory_system.diagnostics.MotionSensorManager') as manager_class:
        manager = MagicMock()
        manager.is_supported.return_value = False
        manager_class.return_value = manager
        display_ok, motion_ok, audio_ok, _ = run_startup_diagnostics(cfg)
        assert (display_ok, motion_ok, audio_ok) == (False, False, True)


def test_diagnostics_audio_failure(mock_display_init, mock_motion_manager, mock_supported, mock_audio, cfg):
    mock_audio.play_sound.return_value = False
    with patch('pi_inventory_system.diagnostics.display_text', return_value=True):
        _, _, audio_ok, _ = run_startup_diagnostics(cfg)
        assert audio_ok is False
