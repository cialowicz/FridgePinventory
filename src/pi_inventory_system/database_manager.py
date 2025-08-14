# Database manager module - thread-safe database operations with proper resource management

import sqlite3
import os
import glob
import logging
import threading
from typing import List, Optional, ContextManager
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from .config_manager import config
from .inventory_item import InventoryItem

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Thread-safe database manager for the FridgePinventory system."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the database manager.
        
        Args:
            db_path: Path to the database file. If None, uses config default.
        """
        self._db_path = db_path or config.get_database_path()
        self._lock = threading.RLock()
        self._initialized = False
        self.initialize()
    
    def initialize(self) -> None:
        """Initialize the database with all pending migrations."""
        with self._lock:
            if self._initialized:
                return
            
            try:
                # Test connection first
                with self._get_connection() as conn:
                    # Create migrations table if it doesn't exist
                    cursor = conn.cursor()
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS migrations (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            migration_name TEXT NOT NULL UNIQUE,
                            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    conn.commit()
                    
                    # Run all pending migrations
                    pending_migrations = self._get_pending_migrations(conn)
                    if pending_migrations:
                        logger.info(f"Found {len(pending_migrations)} pending migrations")
                        for migration_file in pending_migrations:
                            self._run_migration(conn, migration_file)
                    else:
                        logger.info("No pending migrations found")
                
                self._initialized = True
                logger.info(f"Database initialized successfully at {self._db_path}")
                    
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                raise
    
    @contextmanager
    def _get_connection(self) -> ContextManager[sqlite3.Connection]:
        """Get a database connection with proper resource management."""
        conn = None
        try:
            # Get database configuration
            db_config = config.get_database_advanced_config()
            timeout = db_config.get('timeout', 30.0)
            
            conn = sqlite3.connect(
                self._db_path, 
                timeout=timeout,
                isolation_level=None  # Autocommit mode
            )
            conn.row_factory = sqlite3.Row
            
            # Configure database based on settings
            if db_config.get('wal_mode', True):
                conn.execute("PRAGMA journal_mode=WAL")
            
            sync_mode = db_config.get('synchronous_mode', 'NORMAL')
            conn.execute(f"PRAGMA synchronous={sync_mode}")
            
            cache_size = db_config.get('cache_size', 1000)
            conn.execute(f"PRAGMA cache_size={cache_size}")
            
            temp_store = db_config.get('temp_store', 'memory')
            conn.execute(f"PRAGMA temp_store={temp_store}")
            
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def _get_migrations_dir(self) -> str:
        """Get the path to the migrations directory."""
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent
        return str(project_root / 'migrations')
    
    def _get_pending_migrations(self, conn: sqlite3.Connection) -> List[str]:
        """Get a list of pending migrations that haven't been run yet."""
        # Get all migration files
        migrations_dir = self._get_migrations_dir()
        migration_files = sorted(glob.glob(os.path.join(migrations_dir, '*.sql')))
        
        # Get migrations that have already been run
        cursor = conn.cursor()
        cursor.execute("SELECT migration_name FROM migrations")
        applied_migrations = {row[0] for row in cursor.fetchall()}
        
        # Filter out migrations that have already been run
        pending_migrations = []
        for migration_file in migration_files:
            migration_name = os.path.basename(migration_file)
            if migration_name not in applied_migrations:
                pending_migrations.append(migration_file)
        
        return pending_migrations
    
    def _run_migration(self, conn: sqlite3.Connection, migration_file: str) -> None:
        """Run a single migration file."""
        migration_name = os.path.basename(migration_file)
        
        try:
            # Read and execute the migration
            with open(migration_file, 'r') as f:
                sql = f.read()
            
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            
            # Execute the migration SQL
            cursor.executescript(sql)
            
            # Record that the migration was run
            cursor.execute(
                "INSERT INTO migrations (migration_name) VALUES (?)",
                (migration_name,)
            )
            
            cursor.execute("COMMIT")
            logger.info(f"Successfully ran migration: {migration_name}")
            
        except Exception as e:
            cursor.execute("ROLLBACK")
            logger.error(f"Error running migration {migration_name}: {e}")
            raise
    
    def get_current_quantity(self, item_name: str) -> int:
        """Get the current quantity of an item."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item_name,))
                result = cursor.fetchone()
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
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("BEGIN TRANSACTION")
                    
                    # Get current quantity
                    cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
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
                    
                    # Record in history
                    cursor.execute(
                        """INSERT INTO inventory_history 
                           (item_name, previous_quantity, new_quantity, operation_type)
                           VALUES (?, ?, ?, 'add')""",
                        (item.item_name, current, new_quantity)
                    )
                    
                    cursor.execute("COMMIT")
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
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("BEGIN TRANSACTION")
                    
                    # Get current quantity
                    cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
                    result = cursor.fetchone()
                    current = result['quantity'] if result else 0
                    
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
                    
                    cursor.execute("COMMIT")
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
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("BEGIN TRANSACTION")
                    
                    # Get current quantity
                    cursor.execute("SELECT quantity FROM inventory WHERE item_name = ?", (item.item_name,))
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
                    
                    # Record in history
                    cursor.execute(
                        """INSERT INTO inventory_history 
                           (item_name, previous_quantity, new_quantity, operation_type)
                           VALUES (?, ?, ?, 'set')""",
                        (item.item_name, current, item.quantity)
                    )
                    
                    cursor.execute("COMMIT")
                    return True
            except Exception as e:
                logger.error(f"Error setting item {item_name}: {e}")
                return False
    
    def undo_last_change(self) -> tuple[bool, Optional[str]]:
        """Undo the last inventory change.
        
        Returns:
            Tuple of (success, item_name) where item_name is the affected item
        """
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("BEGIN TRANSACTION")
                    
                    # Get the last change
                    cursor.execute(
                        """SELECT * FROM inventory_history 
                           ORDER BY id DESC LIMIT 1"""
                    )
                    last_change = cursor.fetchone()
                    
                    if not last_change:
                        cursor.execute("ROLLBACK")
                        return False, None
                        
                    # Store the history ID to delete later
                    history_id = last_change['id']
                    item_name = last_change['item_name']
                    previous_quantity = last_change['previous_quantity']
                    
                    # Update inventory directly
                    if previous_quantity == 0:
                        # Remove the item entirely if previous quantity was 0
                        cursor.execute(
                            "DELETE FROM inventory WHERE item_name = ?",
                            (item_name,)
                        )
                    else:
                        cursor.execute(
                            "UPDATE inventory SET quantity = ? WHERE item_name = ?",
                            (previous_quantity, item_name)
                        )
                    
                    # Remove the change from history
                    cursor.execute(
                        "DELETE FROM inventory_history WHERE id = ?",
                        (history_id,)
                    )
                    
                    cursor.execute("COMMIT")
                    return True, item_name
            except Exception as e:
                logger.error(f"Error undoing last change: {e}")
                return False, None
    
    def get_inventory(self) -> List[tuple[str, int]]:
        """Get the current inventory state."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT item_name, quantity FROM inventory WHERE quantity > 0")
                return [(row['item_name'], row['quantity']) for row in cursor.fetchall()]


# Factory function to create database manager instances
def create_database_manager(db_path: Optional[str] = None) -> DatabaseManager:
    """Create a new database manager instance.
    
    Args:
        db_path: Path to the database file. If None, uses config default.
        
    Returns:
        DatabaseManager instance
    """
    return DatabaseManager(db_path)


# Default database manager instance for backward compatibility
# This will be replaced with dependency injection in the future
_default_db_manager = None

def get_default_db_manager() -> DatabaseManager:
    """Get the default database manager instance."""
    global _default_db_manager
    if _default_db_manager is None:
        _default_db_manager = create_database_manager()
    return _default_db_manager

# Backward compatibility alias
db_manager = get_default_db_manager()
