"""Common test fixtures for the pi_inventory_system tests."""

import os
import pytest
from unittest.mock import patch, MagicMock
from pi_inventory_system.inventory_db import init_db, get_db, close_db, get_migrations_dir, run_migration

@pytest.fixture
def mock_raspberry_pi():
    """Mock Raspberry Pi environment for display and GPIO tests."""
    with patch('pi_inventory_system.display_manager.is_display_supported') as mock_is_supported:
        mock_is_supported.return_value = True  # Default to True for tests expecting display support
        yield mock_is_supported

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