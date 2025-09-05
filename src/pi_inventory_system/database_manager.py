# Simplified database manager for single-threaded Pi application

import sqlite3
import os
import glob
import logging
import threading
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from .config_manager import config
from .inventory_item import InventoryItem

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Simple database manager optimized for Raspberry Pi with SQLite."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the database manager.
        
        Args:
            db_path: Path to the database file. If None, uses config default.
        """
        self._db_path = db_path or config.get_database_path()
        self._lock = threading.RLock()
        self._connection = None
        self._initialized = False
        self.initialize()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create the database connection.
        
        For a single-threaded Pi application, we maintain one connection
        for better performance and simplicity.
        """
        if self._connection is None:
            try:
                # Simple connection with sensible defaults for Pi
                self._connection = sqlite3.connect(
                    self._db_path, 
                    timeout=30.0,
                    isolation_level=None  # Autocommit mode
                )
                self._connection.row_factory = sqlite3.Row
                
                # Optimize for Pi's limited resources
                self._connection.execute("PRAGMA journal_mode=WAL")
                self._connection.execute("PRAGMA synchronous=NORMAL")
                self._connection.execute("PRAGMA cache_size=500")
                self._connection.execute("PRAGMA temp_store=MEMORY")
                
                logger.info(f"Database connection established to {self._db_path}")
                
            except Exception as e:
                logger.error(f"Failed to create database connection: {e}")
                self._connection = None
                raise
        
        return self._connection
    
    @contextmanager
    def _transaction(self):
        """Simple transaction context manager."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN")
            yield conn
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise
        finally:
            cursor.close()
    
    def initialize(self) -> None:
        """Initialize the database with all pending migrations."""
        with self._lock:
            if self._initialized:
                return
            
            try:
                conn = self._get_connection()
                
                # Create migrations table
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS migrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        migration_name TEXT NOT NULL UNIQUE,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.close()
                
                # Run pending migrations
                self._run_migrations(conn)
                
                self._initialized = True
                logger.info("Database initialized successfully")
                    
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                raise
    
    def _run_migrations(self, conn: sqlite3.Connection):
        """Run all pending migrations."""
        # Get migrations directory
        current_dir = Path(__file__).parent
        migrations_dir = current_dir.parent.parent / 'migrations'
        
        if not migrations_dir.exists():
            logger.info("No migrations directory found")
            return
        
        # Get applied migrations
        cursor = conn.cursor()
        cursor.execute("SELECT migration_name FROM migrations")
        applied = {row[0] for row in cursor.fetchall()}
        
        # Run pending migrations
        migration_files = sorted(migrations_dir.glob('*.sql'))
        for migration_file in migration_files:
            migration_name = migration_file.name
            if migration_name not in applied:
                logger.info(f"Running migration: {migration_name}")
                
                # Read and execute migration
                sql = migration_file.read_text()
                cursor.executescript(sql)
                
                # Record migration
                cursor.execute(
                    "INSERT INTO migrations (migration_name) VALUES (?)",
                    (migration_name,)
                )
        
        cursor.close()
    
    def get_current_quantity(self, item_name: str) -> int:
        """Get the current quantity of an item."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT quantity FROM inventory WHERE item_name = ?", 
                (item_name,)
            )
            result = cursor.fetchone()
            cursor.close()
            return result['quantity'] if result else 0
    
    def add_item(self, item_name: str, quantity: int) -> bool:
        """Add items to inventory."""
        try:
            item = InventoryItem(item_name=item_name, quantity=quantity)
        except ValueError as e:
            logger.warning(f"Invalid item data: {e}")
            return False
            
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    
                    # Get current quantity
                    cursor.execute(
                        "SELECT quantity FROM inventory WHERE item_name = ?",
                        (item.item_name,)
                    )
                    result = cursor.fetchone()
                    current = result['quantity'] if result else 0
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
                    
                    # Record history
                    cursor.execute(
                        """INSERT INTO inventory_history 
                           (item_name, previous_quantity, new_quantity, operation_type)
                           VALUES (?, ?, ?, 'add')""",
                        (item.item_name, current, new_quantity)
                    )
                    
                    cursor.close()
                    return True
                    
            except Exception as e:
                logger.error(f"Error adding item {item_name}: {e}")
                return False
    
    def remove_item(self, item_name: str, quantity: int) -> bool:
        """Remove items from inventory."""
        try:
            item = InventoryItem(item_name=item_name, quantity=quantity)
        except ValueError as e:
            logger.warning(f"Invalid item data: {e}")
            return False
            
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    
                    # Get current quantity
                    cursor.execute(
                        "SELECT quantity FROM inventory WHERE item_name = ?",
                        (item.item_name,)
                    )
                    result = cursor.fetchone()
                    current = result['quantity'] if result else 0
                    
                    # Calculate new quantity (allow going to 0)
                    new_quantity = max(0, current - item.quantity)
                    
                    # Update inventory
                    cursor.execute(
                        "UPDATE inventory SET quantity = ? WHERE item_name = ?",
                        (new_quantity, item.item_name)
                    )
                    
                    # Record history
                    cursor.execute(
                        """INSERT INTO inventory_history 
                           (item_name, previous_quantity, new_quantity, operation_type)
                           VALUES (?, ?, ?, 'remove')""",
                        (item.item_name, current, new_quantity)
                    )
                    
                    cursor.close()
                    return True
                    
            except Exception as e:
                logger.error(f"Error removing item {item_name}: {e}")
                return False
    
    def set_item(self, item_name: str, quantity: int) -> bool:
        """Set the quantity of an item."""
        try:
            item = InventoryItem(item_name=item_name, quantity=quantity)
        except ValueError as e:
            logger.warning(f"Invalid item data: {e}")
            return False
            
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    
                    # Get current quantity
                    cursor.execute(
                        "SELECT quantity FROM inventory WHERE item_name = ?",
                        (item.item_name,)
                    )
                    result = cursor.fetchone()
                    current = result['quantity'] if result else 0
                    
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
                    
                    # Record history
                    cursor.execute(
                        """INSERT INTO inventory_history 
                           (item_name, previous_quantity, new_quantity, operation_type)
                           VALUES (?, ?, ?, 'set')""",
                        (item.item_name, current, item.quantity)
                    )
                    
                    cursor.close()
                    return True
                    
            except Exception as e:
                logger.error(f"Error setting item {item_name}: {e}")
                return False
    
    def undo_last_change(self) -> tuple[bool, Optional[str]]:
        """Undo the last inventory change.
        
        Returns:
            Tuple of (success, item_name)
        """
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    
                    # Get last change
                    cursor.execute(
                        """SELECT * FROM inventory_history 
                           ORDER BY id DESC LIMIT 1"""
                    )
                    last_change = cursor.fetchone()
                    
                    if not last_change:
                        cursor.close()
                        return False, None
                    
                    history_id = last_change['id']
                    item_name = last_change['item_name']
                    previous_quantity = last_change['previous_quantity']
                    
                    # Restore previous quantity
                    if previous_quantity == 0:
                        cursor.execute(
                            "DELETE FROM inventory WHERE item_name = ?",
                            (item_name,)
                        )
                    else:
                        cursor.execute(
                            "UPDATE inventory SET quantity = ? WHERE item_name = ?",
                            (previous_quantity, item_name)
                        )
                    
                    # Remove history entry
                    cursor.execute(
                        "DELETE FROM inventory_history WHERE id = ?",
                        (history_id,)
                    )
                    
                    cursor.close()
                    return True, item_name
                    
            except Exception as e:
                logger.error(f"Error undoing last change: {e}")
                return False, None
    
    def get_inventory(self) -> List[tuple[str, int]]:
        """Get the current inventory state."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT item_name, quantity FROM inventory WHERE quantity > 0"
            )
            result = [(row['item_name'], row['quantity']) for row in cursor.fetchall()]
            cursor.close()
            return result
    
    def cleanup(self):
        """Close the database connection."""
        with self._lock:
            if self._connection:
                try:
                    self._connection.close()
                    logger.info("Database connection closed")
                except Exception as e:
                    logger.error(f"Error closing database: {e}")
                finally:
                    self._connection = None


# Factory function
def create_database_manager(db_path: Optional[str] = None) -> DatabaseManager:
    """Create a new database manager instance."""
    return DatabaseManager(db_path)


# Default instance management
_default_db_manager = None

def get_default_db_manager() -> DatabaseManager:
    """Get the default database manager instance."""
    global _default_db_manager
    if _default_db_manager is None:
        _default_db_manager = create_database_manager()
    return _default_db_manager

# Backward compatibility
db_manager = get_default_db_manager()
