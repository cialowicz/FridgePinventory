# Tests for diagnostics module

import pytest
from unittest.mock import patch, MagicMock
from pi_inventory_system.diagnostics import run_startup_diagnostics

@pytest.fixture
def mock_display():
    with patch('pi_inventory_system.diagnostics.initialize_display') as mock:
        mock_display = MagicMock()
        mock.return_value = mock_display
        yield mock_display

@pytest.fixture
def mock_motion_sensor():
    with patch('pi_inventory_system.diagnostics.detect_motion') as mock:
        mock.return_value = False
        yield mock

@pytest.fixture
def mock_supported():
    with patch('pi_inventory_system.diagnostics.is_display_supported') as mock_display, \
         patch('pi_inventory_system.diagnostics.is_motion_sensor_supported') as mock_motion:
        mock_display.return_value = True
        mock_motion.return_value = True
        yield mock_display, mock_motion

def test_diagnostics_display_success(mock_display, mock_motion_sensor, mock_supported):
    """Test successful display diagnostics."""
    with patch('pi_inventory_system.diagnostics.display_text') as mock_display_text:
        mock_display_text.return_value = True
        display_ok, motion_sensor_ok = run_startup_diagnostics()
        assert display_ok is True
        assert motion_sensor_ok is True
        mock_display_text.assert_called_once_with(mock_display, "FridgePinventory\nstarting up...")

def test_diagnostics_display_failure(mock_display, mock_motion_sensor, mock_supported):
    """Test display diagnostics failure."""
    with patch('pi_inventory_system.diagnostics.display_text') as mock_display_text:
        mock_display_text.return_value = False
        display_ok, motion_sensor_ok = run_startup_diagnostics()
        assert display_ok is False
        assert motion_sensor_ok is True

def test_diagnostics_motion_sensor_failure(mock_display, mock_motion_sensor, mock_supported):
    """Test motion sensor diagnostics failure."""
    mock_motion_sensor.side_effect = Exception("Sensor error")
    with patch('pi_inventory_system.diagnostics.display_text') as mock_display_text:
        mock_display_text.return_value = True
        display_ok, motion_sensor_ok = run_startup_diagnostics()
        assert display_ok is True
        assert motion_sensor_ok is False

def test_diagnostics_platform_not_supported():
    """Test diagnostics on unsupported platform."""
    with patch('pi_inventory_system.diagnostics.is_display_supported') as mock_display, \
         patch('pi_inventory_system.diagnostics.is_motion_sensor_supported') as mock_motion:
        mock_display.return_value = False
        mock_motion.return_value = False
        display_ok, motion_sensor_ok = run_startup_diagnostics()
        assert display_ok is False
        assert motion_sensor_ok is False 