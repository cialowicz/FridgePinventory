"""Common test fixtures for the pi_inventory_system tests."""

import os
import pytest
from unittest.mock import patch, MagicMock
from pi_inventory_system.inventory_db import init_db, get_db, close_db, get_migrations_dir, run_migration

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
def db_connection():
    """Set up test database connection and run migrations."""
    # Initialize in-memory database
    init_db(':memory:')
    conn = get_db()
    cursor = conn.cursor()

    # Get migrations directory
    migrations_dir = get_migrations_dir()
    
    # Run migrations in order
    for migration_file in sorted(os.listdir(migrations_dir)):
        if migration_file.endswith('.sql'):
            migration_path = os.path.join(migrations_dir, migration_file)
            run_migration(conn, migration_path)

    yield conn, cursor
    close_db()

@pytest.fixture
def mock_display():
    """Mock display for testing display-related functionality."""
    mock_display = MagicMock()
    mock_display.WIDTH = 400
    mock_display.HEIGHT = 300
    return mock_display 