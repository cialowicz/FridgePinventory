# Database manager module - replaces global state management

import sqlite3
import os
import glob
import logging
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from .config_manager import config
from .inventory_item import InventoryItem

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Singleton database manager for the FridgePinventory system."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._connection = None
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.initialize()
    
    def initialize(self, db_path: Optional[str] = None) -> None:
        """Initialize the database with all pending migrations."""
        if self._connection is not None:
            return
        
        # Use configured database path if not provided
        if db_path is None:
            db_path = config.get_database_path()
        
        try:
            self._connection = sqlite3.connect(db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            
            # Create migrations table if it doesn't exist
            cursor = self._connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_name TEXT NOT NULL UNIQUE,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self._connection.commit()
            
            # Run all pending migrations
            pending_migrations = self.get_pending_migrations()
            if pending_migrations:
                logger.info(f"Found {len(pending_migrations)} pending migrations")
                for migration_file in pending_migrations:
                    self.run_migration(migration_file)
            else:
                logger.info("No pending migrations found")
            
            self._initialized = True
            logger.info(f"Database initialized successfully at {db_path}")
                
        except Exception as e:
            if self._connection:
                self._connection.close()
                self._connection = None
            logger.error(f"Failed to initialize database: {e}")
            raise e
    
    def get_connection(self) -> sqlite3.Connection:
        """Get the database connection."""
        if self._connection is None:
            self.initialize()
        return self._connection
    
    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            self._initialized = False
            logger.info("Database connection closed")
    
    def get_migrations_dir(self) -> str:
        """Get the path to the migrations directory."""
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent
        return str(project_root / 'migrations')
    
    def get_pending_migrations(self) -> List[str]:
        """Get a list of pending migrations that haven't been run yet."""
        # Get all migration files
        migrations_dir = self.get_migrations_dir()
        migration_files = sorted(glob.glob(os.path.join(migrations_dir, '*.sql')))
        
        # Get migrations that have already been run
        cursor = self._connection.cursor()
        cursor.execute("SELECT migration_name FROM migrations")
        applied_migrations = {row[0] for row in cursor.fetchall()}
        
        # Filter out migrations that have already been run
        pending_migrations = []
        for migration_file in migration_files:
            migration_name = os.path.basename(migration_file)
            if migration_name not in applied_migrations:
                pending_migrations.append(migration_file)
        
        return pending_migrations
    
    def run_migration(self, migration_file: str) -> None:
        """Run a single migration file."""
        migration_name = os.path.basename(migration_file)
        
        try:
            # Read and execute the migration
            with open(migration_file, 'r') as f:
                sql = f.read()
            
            cursor = self._connection.cursor()
            cursor.executescript(sql)
            
            # Record that the migration was run
            cursor.execute(
                "INSERT INTO migrations (migration_name) VALUES (?)",
                (migration_name,)
            )
            
            self._connection.commit()
            logger.info(f"Successfully ran migration: {migration_name}")
            
        except Exception as e:
            self._connection.rollback()
            logger.error(f"Error running migration {migration_name}: {e}")
            raise
    
    def get_current_quantity(self, item_name: str) -> int:
        """Get the current quantity of an item."""
        cursor = self._connection.cursor()
        cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item_name,))
        result = cursor.fetchone()
        return result['quantity'] if result else 0
    
    def add_item(self, item_name: str, quantity: int) -> bool:
        """Add items to inventory."""
        try:
            item = InventoryItem(item_name=item_name, quantity=quantity)
        except ValueError:
            return False
            
        cursor = self._connection.cursor()
        
        try:
            cursor.execute("BEGIN")
            
            # Get current quantity
            current = self.get_current_quantity(item.item_name)
            new_quantity = current + item.quantity
            
            # Update inventory
            if current == 0:
                cursor.execute(
                    "INSERT INTO inventory (item_name, quantity) VALUES (?, ?)",
                    (item.item_name, new_quantity)
                )
            else:
                cursor.execute(
                    "UPDATE inventory SET quantity = ? WHERE item_name = ?",
                    (new_quantity, item.item_name)
                )
            
            # Record in history
            cursor.execute(
                """INSERT INTO inventory_history 
                   (item_name, previous_quantity, new_quantity, operation_type)
                   VALUES (?, ?, ?, 'add')""",
                (item.item_name, current, new_quantity)
            )
            
            self._connection.commit()
            return True
        except Exception:
            self._connection.rollback()
            return False
    
    def remove_item(self, item_name: str, quantity: int) -> bool:
        """Remove items from inventory."""
        try:
            item = InventoryItem(item_name=item_name, quantity=quantity)
        except ValueError:
            return False
            
        cursor = self._connection.cursor()
        
        try:
            cursor.execute("BEGIN")
            
            # Get current quantity
            current = self.get_current_quantity(item.item_name)
            if current < item.quantity:
                new_quantity = 0
            else:
                new_quantity = current - item.quantity
            
            # Update inventory
            cursor.execute(
                "UPDATE inventory SET quantity = ? WHERE item_name = ?",
                (new_quantity, item.item_name)
            )
            
            # Record in history
            cursor.execute(
                """INSERT INTO inventory_history 
                   (item_name, previous_quantity, new_quantity, operation_type)
                   VALUES (?, ?, ?, 'remove')""",
                (item.item_name, current, new_quantity)
            )
            
            self._connection.commit()
            return True
        except Exception:
            self._connection.rollback()
            return False
    
    def set_item(self, item_name: str, quantity: int) -> bool:
        """Set the quantity of an item."""
        try:
            item = InventoryItem(item_name=item_name, quantity=quantity)
        except ValueError:
            return False
            
        cursor = self._connection.cursor()
        
        try:
            cursor.execute("BEGIN")
            
            # Get current quantity
            current = self.get_current_quantity(item.item_name)
            
            # Update inventory
            if current == 0:
                cursor.execute(
                    "INSERT INTO inventory (item_name, quantity) VALUES (?, ?)",
                    (item.item_name, item.quantity)
                )
            else:
                cursor.execute(
                    "UPDATE inventory SET quantity = ? WHERE item_name = ?",
                    (item.quantity, item.item_name)
                )
            
            # Record in history
            cursor.execute(
                """INSERT INTO inventory_history 
                   (item_name, previous_quantity, new_quantity, operation_type)
                   VALUES (?, ?, ?, 'set')""",
                (item.item_name, current, item.quantity)
            )
            
            self._connection.commit()
            return True
        except Exception:
            self._connection.rollback()
            return False
    
    def undo_last_change(self) -> bool:
        """Undo the last inventory change."""
        cursor = self._connection.cursor()
        
        try:
            cursor.execute("BEGIN")
            
            # Get the last change
            cursor.execute(
                """SELECT * FROM inventory_history 
                   ORDER BY id DESC LIMIT 1"""
            )
            last_change = cursor.fetchone()
            
            if not last_change:
                self._connection.rollback()
                return False
                
            # Store the history ID to delete later
            history_id = last_change['id']
            
            # Update inventory directly instead of using add/remove/set
            cursor.execute(
                "UPDATE inventory SET quantity = ? WHERE item_name = ?",
                (last_change['previous_quantity'], last_change['item_name'])
            )
            
            # Remove the change from history
            cursor.execute(
                "DELETE FROM inventory_history WHERE id = ?",
                (history_id,)
            )
            
            self._connection.commit()
            return True
        except Exception:
            self._connection.rollback()
            return False
    
    def get_inventory(self) -> List[tuple]:
        """Get the current inventory state."""
        cursor = self._connection.cursor()
        cursor.execute("SELECT item_name, quantity FROM inventory WHERE quantity > 0")
        return [(row['item_name'], row['quantity']) for row in cursor.fetchall()]


# Global database manager instance
db_manager = DatabaseManager()
