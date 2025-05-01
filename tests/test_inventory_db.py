# Tests for inventory database module

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from src.pi_inventory_system.inventory_db import (
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
from src.pi_inventory_system.inventory_item import InventoryItem


class TestInventoryDB(unittest.TestCase):
    """Test cases for inventory database functionality."""

    def setUp(self):
        """Set up test environment."""
        # Initialize in-memory database
        init_db(':memory:')
        self.conn = get_db()
        self.cursor = self.conn.cursor()

        # Create required tables
        self.cursor.executescript('''
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
        self.conn.commit()

    def tearDown(self):
        """Clean up test environment."""
        close_db()

    def test_init_db(self):
        """Test database initialization."""
        close_db()  # Close the existing connection
        with patch('src.pi_inventory_system.inventory_db.sqlite3') as mock_sqlite:
            mock_conn = MagicMock()
            mock_sqlite.connect.return_value = mock_conn
            init_db()
            mock_sqlite.connect.assert_called_once()
            mock_conn.commit.assert_called_once()

    def test_migrations(self):
        """Test database migrations."""
        # Create a temporary migrations directory
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.pi_inventory_system.inventory_db.get_migrations_dir', return_value=temp_dir):
                # Create a test migration file
                migration_path = os.path.join(temp_dir, '001_test_migration.sql')
                with open(migration_path, 'w') as f:
                    f.write('CREATE TABLE test (id INTEGER PRIMARY KEY);')

                # Run the migration
                run_migration(self.conn, migration_path)

                # Verify migration was recorded
                self.cursor.execute("SELECT migration_name FROM migrations WHERE migration_name = '001_test_migration.sql'")
                result = self.cursor.fetchone()
                self.assertIsNotNone(result)

                # Verify table was created
                self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")
                result = self.cursor.fetchone()
                self.assertIsNotNone(result)

    def test_add_item(self):
        """Test adding items to inventory."""
        # Add a new item
        item = InventoryItem("test_item", 5)
        self.assertTrue(add_item(item.item_name, item.quantity))
        
        # Verify item was added
        self.cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
        result = self.cursor.fetchone()
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 5)

        # Add more of the same item
        self.assertTrue(add_item(item.item_name, 3))
        self.cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
        result = self.cursor.fetchone()
        self.assertEqual(result[0], 8)

    def test_remove_item(self):
        """Test removing items from inventory."""
        # Add an item first
        item = InventoryItem("test_item", 5)
        add_item(item.item_name, item.quantity)
        
        # Remove some quantity
        self.assertTrue(remove_item(item.item_name, 2))
        self.cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
        result = self.cursor.fetchone()
        self.assertEqual(result[0], 3)

        # Try to remove more than available
        self.assertTrue(remove_item(item.item_name, 5))  # Should succeed but set quantity to 0
        self.cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
        result = self.cursor.fetchone()
        self.assertEqual(result[0], 0)

    def test_set_item(self):
        """Test setting item quantity."""
        item = InventoryItem("test_item", 5)
        
        # Set quantity for new item
        self.assertTrue(set_item(item.item_name, item.quantity))
        self.cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
        result = self.cursor.fetchone()
        self.assertEqual(result[0], 5)

        # Update existing item
        self.assertTrue(set_item(item.item_name, 10))
        self.cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
        result = self.cursor.fetchone()
        self.assertEqual(result[0], 10)

    def test_get_inventory(self):
        """Test retrieving inventory."""
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
        self.assertEqual(len(inventory), 3)
        inventory_dict = {item[0]: item[1] for item in inventory}
        self.assertEqual(inventory_dict["item1"], 5)
        self.assertEqual(inventory_dict["item2"], 3)
        self.assertEqual(inventory_dict["item3"], 7)

    def test_undo_last_change(self):
        """Test undoing the last change."""
        item = InventoryItem("test_item", 5)
        
        # Add an item
        add_item(item.item_name, item.quantity)
        
        # Modify it
        set_item(item.item_name, 10)
        
        # Undo the change
        self.assertTrue(undo_last_change())
        self.cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
        result = self.cursor.fetchone()
        self.assertEqual(result[0], 5)

    def test_get_current_quantity(self):
        """Test getting current quantity of an item."""
        item = InventoryItem("test_item", 5)
        
        # Check non-existent item
        self.assertEqual(get_current_quantity(item.item_name), 0)
        
        # Add item and check
        add_item(item.item_name, item.quantity)
        self.assertEqual(get_current_quantity(item.item_name), 5)


if __name__ == '__main__':
    unittest.main()
