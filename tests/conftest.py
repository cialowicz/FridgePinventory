"""Common test fixtures for the pi_inventory_system tests."""

import os
import pytest
from unittest.mock import patch, MagicMock
from pi_inventory_system.database_manager import db_manager

@pytest.fixture(autouse=True)
def mock_config():
    """Mock configuration system for all tests."""
    mock_config = MagicMock()
    mock_config.get_database_path.return_value = ':memory:'
    mock_config.get_font_config.return_value = {
        'path': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        'size': 16,
        'fallback_size': 12
    }
    mock_config.get_layout_config.return_value = {
        'items_per_row': 2,
        'lozenge_width_margin': 30,
        'lozenge_height': 40,
        'spacing': 10,
        'margin': 10
    }
    mock_config.get_audio_config.return_value = {
        'voice_recognition': {
            'timeout': 5,
            'phrase_time_limit': 10,
            'engine': 'sphinx',
            'device_index': None
        },
        'text_to_speech': {
            'rate': 150,
            'volume': 0.9,
            'voice_id': None
        },
        'feedback_sounds': {
            'success_sound': 'sounds/success.wav',
            'error_sound': 'sounds/error.wav'
        }
    }
    mock_config.get_command_config.return_value = {
        'similarity_threshold': 0.8,
        'special_quantities': {
            'a': 1,
            'an': 1,
            'few': 3,
            'several': 3
        }
    }
    mock_config.get_system_config.return_value = {
        'main_loop_delay': 0.1,
        'log_level': 'INFO',
        'enable_diagnostics': True
    }
    mock_config.get.return_value = {}
    
    with patch('pi_inventory_system.config_manager.config', mock_config):
        yield mock_config

@pytest.fixture
def mock_raspberry_pi():
    """Mock Raspberry Pi environment for display and GPIO tests."""
    # This mock ensures that when display_manager.py is imported and performs its initial checks,
    # it believes it's on a Raspberry Pi and that the inky library's auto function is available.
    mock_auto_function = MagicMock(name="mock_inky_auto_dot_auto_globally")
    with patch('pi_inventory_system.display_manager._is_raspberry_pi', return_value=True) as mock_is_pi_internal, \
         patch('inky.auto.auto', mock_auto_function) as mock_inky_auto_import_source:
        # Because 'inky.auto.auto' is patched, the import in display_manager.py:
        #   from inky.auto import auto as auto_inky_display
        # will result in display_manager.auto_inky_display being mock_auto_function.
        # Consequently, INKY_AVAILABLE will be set to True in display_manager.py.
        # And display_manager.is_display_supported() will evaluate to True.
        yield mock_is_pi_internal, mock_inky_auto_import_source

@pytest.fixture
def mock_gpio_environment():
    """Mock GPIO environment for motion sensor tests."""
    # Reset the _gpio_initialized state
    import pi_inventory_system.motion_sensor as motion_sensor
    motion_sensor._gpio_initialized = False

    with patch('pi_inventory_system.motion_sensor._is_raspberry_pi') as mock_is_pi, \
         patch('pi_inventory_system.motion_sensor.GPIO', create=True) as mock_gpio:  # Added create=True for GPIO as it might not exist if not on Pi
        
        mock_is_pi.return_value = True # Simulate running on a Pi
        
        yield mock_is_pi, mock_gpio

@pytest.fixture
def db_connection(tmp_path):
    """Set up test database connection and run migrations."""
    # Initialize a clean database for each test
    db_manager.initialize(db_path=str(tmp_path / "test.db"))
    
    yield db_manager.get_connection()
    
    # Clean up the database connection
    db_manager.close()

@pytest.fixture
def mock_display():
    """Mock display for testing display-related functionality."""
    mock_display = MagicMock()
    mock_display.WIDTH = 400
    mock_display.HEIGHT = 300
    return mock_display
