# Tests for inventory database module

import unittest
import sqlite3
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from pi_inventory_system.inventory_db import (
    init_db, get_db, add_item, remove_item, set_item,
    get_inventory, undo_last_change, get_current_quantity,
    close_db
)


def print_db_state():
    """Print the current state of both tables."""
    conn = get_db()
    cursor = conn.cursor()
    
    print("\nInventory table:")
    cursor.execute("SELECT * FROM inventory")
    print(cursor.fetchall())
    
    print("\nHistory table:")
    cursor.execute("SELECT * FROM inventory_history ORDER BY id")
    print(cursor.fetchall())


class TestInventoryDB(unittest.TestCase):
    """Integration tests using a real SQLite database."""
    
    def setUp(self):
        """Set up an in-memory database for testing."""
        # Create a temporary migrations directory
        self.temp_dir = tempfile.mkdtemp()
        self.migrations_dir = os.path.join(self.temp_dir, 'migrations')
        os.makedirs(self.migrations_dir)
        
        # Copy all migration files to the temporary directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        actual_migrations_dir = os.path.join(project_root, 'migrations')
        
        for migration_file in os.listdir(actual_migrations_dir):
            if migration_file.endswith('.sql'):
                src = os.path.join(actual_migrations_dir, migration_file)
                dst = os.path.join(self.migrations_dir, migration_file)
                shutil.copy2(src, dst)
        
        # Patch the migrations directory path
        self.patchers = [
            patch('pi_inventory_system.inventory_db._db_connection', None),
            patch('pi_inventory_system.inventory_db.get_migrations_dir', return_value=self.migrations_dir)
        ]
        for patcher in self.patchers:
            patcher.start()
        
        # Initialize the database
        init_db(':memory:')
        self.conn = get_db()
    
    def tearDown(self):
        """Clean up after tests."""
        # Close the database connection
        close_db()
        
        # Stop all patchers
        for patcher in self.patchers:
            patcher.stop()
        
        # Remove temporary files
        for filename in os.listdir(self.migrations_dir):
            file_path = os.path.join(self.migrations_dir, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)
        os.rmdir(self.migrations_dir)
        os.rmdir(self.temp_dir)
    
    def test_add_item(self):
        """Test adding items to inventory."""
        # Test adding a new item
        add_item("chicken", 5)
        self.assertEqual(get_current_quantity("chicken"), 5)
        
        # Test adding to existing item
        add_item("chicken", 3)
        self.assertEqual(get_current_quantity("chicken"), 8)
    
    def test_remove_item(self):
        """Test removing items from inventory."""
        # Clear any existing items
        self.conn.execute("DELETE FROM inventory")
        self.conn.execute("DELETE FROM inventory_history")
        self.conn.commit()
        
        print("\nInitial state:")
        print_db_state()
        
        # Add some items first
        add_item("beef", 10)
        print("\nAfter adding beef:")
        print_db_state()
        
        # Test removing items
        remove_item("beef", 3)
        print("\nAfter removing 3 beef:")
        print_db_state()
        
        # Verify the quantity
        current = get_current_quantity("beef")
        print(f"\nCurrent quantity: {current}")
        self.assertEqual(current, 7)
        
        # Test removing more than available
        remove_item("beef", 10)
        print("\nAfter removing 10 more beef:")
        print_db_state()
        self.assertEqual(get_current_quantity("beef"), 0)
    
    def test_set_item(self):
        """Test setting item quantities."""
        # Test setting a new item
        set_item("salmon", 4)
        self.assertEqual(get_current_quantity("salmon"), 4)
        
        # Test updating an existing item
        set_item("salmon", 2)
        self.assertEqual(get_current_quantity("salmon"), 2)
    
    def test_get_inventory(self):
        """Test retrieving the entire inventory."""
        # Clear any existing items
        self.conn.execute("DELETE FROM inventory")
        self.conn.commit()
        
        # Add some items
        add_item("chicken", 5)
        add_item("beef", 3)
        
        # Get inventory and verify contents
        inventory = get_inventory()
        self.assertEqual(len(inventory), 2)
        self.assertIn(("chicken", 5), inventory)
        self.assertIn(("beef", 3), inventory)
    
    def test_undo_last_change(self):
        """Test undoing the last inventory change."""
        # Clear any existing items
        self.conn.execute("DELETE FROM inventory")
        self.conn.execute("DELETE FROM inventory_history")
        self.conn.commit()
        
        # Add an item
        add_item("fish", 5)
        self.assertEqual(get_current_quantity("fish"), 5)
        
        # Remove some
        remove_item("fish", 2)
        self.assertEqual(get_current_quantity("fish"), 3)
        
        # Undo the removal
        self.assertTrue(undo_last_change())
        self.assertEqual(get_current_quantity("fish"), 5)
        
        # Undo the addition
        self.assertTrue(undo_last_change())
        self.assertEqual(get_current_quantity("fish"), 0)
        
        # Test undoing when no changes exist
        self.assertFalse(undo_last_change())


class TestInventoryDBUnit(unittest.TestCase):
    """Unit tests using mocks."""
    
    def setUp(self):
        """Set up mock database connection."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.patcher = patch('pi_inventory_system.inventory_db.get_db', return_value=self.mock_conn)
        self.patcher.start()
    
    def tearDown(self):
        """Clean up after tests."""
        self.patcher.stop()
    
    def test_add_item_new(self):
        """Test adding a new item."""
        # Mock get_current_quantity to return 0 for new item
        with patch('pi_inventory_system.inventory_db.get_current_quantity', return_value=0):
            add_item("chicken", 5)
            
            # Verify all operations
            calls = self.mock_cursor.execute.call_args_list
            self.assertEqual(len(calls), 3)  # BEGIN + inventory + history
    
    def test_add_item_existing(self):
        """Test adding to an existing item."""
        # Mock get_current_quantity to return a non-zero value
        with patch('pi_inventory_system.inventory_db.get_current_quantity', return_value=3):
            add_item("chicken", 5)
            
            # Verify all operations
            calls = self.mock_cursor.execute.call_args_list
            self.assertEqual(len(calls), 3)  # BEGIN + inventory + history
    
    def test_remove_item(self):
        """Test removing items."""
        # Mock get_current_quantity to return a non-zero value
        with patch('pi_inventory_system.inventory_db.get_current_quantity', return_value=10):
            remove_item("beef", 3)
            
            # Verify all operations
            calls = self.mock_cursor.execute.call_args_list
            self.assertEqual(len(calls), 3)  # BEGIN + inventory + history
    
    def test_set_item(self):
        """Test setting item quantities."""
        set_item("salmon", 4)
        
        # Verify all operations
        calls = self.mock_cursor.execute.call_args_list
        self.assertEqual(len(calls), 4)  # BEGIN + get_current_quantity + inventory + history


if __name__ == '__main__':
    unittest.main()
