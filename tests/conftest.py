"""Common test fixtures for the pi_inventory_system tests."""

import pytest
from unittest.mock import MagicMock, patch

from pi_inventory_system.config_manager import create_config_manager
from pi_inventory_system.database_manager import create_database_manager


def _build_mock_config():
    mock_config = MagicMock()
    mock_config.get_database_path.return_value = ':memory:'
    mock_config.get_font_config.return_value = {
        'path': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        'size': 16,
        'fallback_size': 12,
    }
    mock_config.get_layout_config.return_value = {
        'items_per_row': 2,
        'lozenge_width_margin': 30,
        'lozenge_height': 40,
        'spacing': 10,
        'margin': 10,
    }
    mock_config.get_audio_config.return_value = {
        'voice_recognition': {
            'timeout': 5,
            'phrase_time_limit': 10,
            'engine': 'sphinx',
            'device_index': None,
        },
        'text_to_speech': {
            'rate': 150,
            'volume': 0.9,
            'voice_id': None,
        },
        'feedback_sounds': {
            'success_sound': 'sounds/success.wav',
            'error_sound': 'sounds/error.wav',
        },
    }
    mock_config.get_command_config.return_value = {
        'similarity_threshold': 0.8,
        'special_quantities': {'a': 1, 'an': 1, 'few': 3, 'several': 3},
    }
    mock_config.get_system_config.return_value = {
        'main_loop_delay': 0.1,
        'log_level': 'INFO',
        'enable_diagnostics': True,
    }
    mock_config.get_nlp_config.return_value = {
        'spacy_model': 'en_core_web_sm',
        'enable_spacy': True,
    }
    mock_config.get_database_advanced_config.return_value = {
        'timeout': 30.0,
        'wal_mode': 'WAL',
        'cache_size': 1000,
        'synchronous_mode': 'NORMAL',
        'temp_store': 'memory',
    }
    mock_config.get_platform_config.return_value = {
        'raspberry_pi_model_file': '/proc/device-tree/model',
        'required_pi_string': 'raspberry pi',
    }
    mock_config.get_hardware_config.return_value = {
        'motion_sensor': {'enabled': True, 'pin': 4},
    }
    mock_config.get.return_value = {}
    return mock_config


@pytest.fixture
def mock_config_manager():
    """Stand-alone mock config manager for tests that take it explicitly."""
    return _build_mock_config()


@pytest.fixture
def mock_raspberry_pi():
    """Force display_manager._is_raspberry_pi to return True."""
    with patch('pi_inventory_system.display_manager._is_raspberry_pi', return_value=True) as m:
        yield m


@pytest.fixture
def db_manager_instance(tmp_path):
    """Create a real on-disk DatabaseManager bound to a tmp file."""
    config = create_config_manager()
    db_manager = create_database_manager(config, db_path=str(tmp_path / "test.db"))
    yield db_manager
    db_manager.cleanup()


@pytest.fixture
def mock_display():
    """MagicMock with the WaveshareDisplay surface area tests rely on."""
    display = MagicMock()
    display.WIDTH = 800
    display.HEIGHT = 480
    display.display_image = MagicMock()
    display.clear = MagicMock()
    display.cleanup = MagicMock()
    return display
