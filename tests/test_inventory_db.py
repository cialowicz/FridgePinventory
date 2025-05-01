# Tests for inventory database module

import os
import sqlite3
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from pi_inventory_system.inventory_db import (
    init_db,
    get_db,
    close_db,
    add_item,
    remove_item,
    set_item,
    get_inventory,
    undo_last_change,
    get_current_quantity,
    get_migrations_dir,
    run_migration
)
from pi_inventory_system.inventory_item import InventoryItem

@pytest.fixture
def db_connection():
    """Set up test environment."""
    # Initialize in-memory database
    init_db(':memory:')
    conn = get_db()
    cursor = conn.cursor()

    # Create required tables
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_name TEXT NOT NULL UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL UNIQUE,
            quantity INTEGER NOT NULL DEFAULT 0,
            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS inventory_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            previous_quantity INTEGER NOT NULL,
            new_quantity INTEGER NOT NULL,
            operation_type TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    yield conn, cursor
    close_db()

def test_init_db():
    """Test database initialization."""
    close_db()  # Close the existing connection
    with patch('pi_inventory_system.inventory_db.sqlite3') as mock_sqlite:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_sqlite.connect.return_value = mock_conn
        
        init_db()
        
        # Verify database connection was created
        mock_sqlite.connect.assert_called_once()
        
        # Verify migrations table was created
        mock_cursor.execute.assert_any_call("""
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_name TEXT NOT NULL UNIQUE,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Verify commit was called
        mock_conn.commit.assert_called_once()

def test_migrations(db_connection):
    """Test database migrations."""
    conn, cursor = db_connection
    # Create a temporary migrations directory
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('pi_inventory_system.inventory_db.get_migrations_dir', return_value=temp_dir):
            # Create a test migration file
            migration_path = os.path.join(temp_dir, '001_test_migration.sql')
            with open(migration_path, 'w') as f:
                f.write('CREATE TABLE test (id INTEGER PRIMARY KEY);')

            # Run the migration
            run_migration(conn, migration_path)

            # Verify migration was recorded
            cursor.execute("SELECT migration_name FROM migrations WHERE migration_name = '001_test_migration.sql'")
            result = cursor.fetchone()
            assert result is not None

            # Verify table was created
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")
            result = cursor.fetchone()
            assert result is not None

def test_add_item(db_connection):
    """Test adding items to inventory."""
    conn, cursor = db_connection
    # Add a new item
    item = InventoryItem("test_item", 5)
    assert add_item(item.item_name, item.quantity)
    
    # Verify item was added
    cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == 5

    # Add more of the same item
    assert add_item(item.item_name, 3)
    cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
    result = cursor.fetchone()
    assert result[0] == 8

def test_remove_item(db_connection):
    """Test removing items from inventory."""
    conn, cursor = db_connection
    # Add an item first
    item = InventoryItem("test_item", 5)
    add_item(item.item_name, item.quantity)
    
    # Remove some quantity
    assert remove_item(item.item_name, 2)
    cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
    result = cursor.fetchone()
    assert result[0] == 3

    # Try to remove more than available
    assert remove_item(item.item_name, 5)  # Should succeed but set quantity to 0
    cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
    result = cursor.fetchone()
    assert result[0] == 0

def test_set_item(db_connection):
    """Test setting item quantity."""
    conn, cursor = db_connection
    item = InventoryItem("test_item", 5)
    
    # Set quantity for new item
    assert set_item(item.item_name, item.quantity)
    cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
    result = cursor.fetchone()
    assert result[0] == 5

    # Update existing item
    assert set_item(item.item_name, 10)
    cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
    result = cursor.fetchone()
    assert result[0] == 10

def test_get_inventory(db_connection):
    """Test retrieving inventory."""
    conn, cursor = db_connection
    # Add some items
    items = [
        InventoryItem("item1", 5),
        InventoryItem("item2", 3),
        InventoryItem("item3", 7)
    ]
    for item in items:
        add_item(item.item_name, item.quantity)
    
    # Get inventory
    inventory = get_inventory()
    assert len(inventory) == 3
    inventory_dict = {item[0]: item[1] for item in inventory}
    assert inventory_dict["item1"] == 5
    assert inventory_dict["item2"] == 3
    assert inventory_dict["item3"] == 7

def test_undo_last_change(db_connection):
    """Test undoing the last change."""
    conn, cursor = db_connection
    item = InventoryItem("test_item", 5)
    
    # Add an item
    add_item(item.item_name, item.quantity)
    
    # Modify it
    set_item(item.item_name, 10)
    
    # Undo the change
    assert undo_last_change()
    cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
    result = cursor.fetchone()
    assert result[0] == 5

def test_get_current_quantity(db_connection):
    """Test getting current quantity of an item."""
    conn, cursor = db_connection
    item = InventoryItem("test_item", 5)
    
    # Check non-existent item
    assert get_current_quantity(item.item_name) == 0
    
    # Add item and check
    add_item(item.item_name, item.quantity)
    assert get_current_quantity(item.item_name) == 5
