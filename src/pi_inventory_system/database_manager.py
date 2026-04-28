# Simplified database manager for single-threaded Pi application

import logging
import sqlite3
import threading
from contextlib import contextmanager
from importlib import resources
from typing import Any, List, Optional

from .exceptions import DatabaseError
from .inventory_item import InventoryItem

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Simple database manager optimized for Raspberry Pi with SQLite."""
    
    def __init__(self, db_path: Optional[str] = None, config_manager: Optional[Any] = None):
        """Initialize the database manager.
        
        Args:
            db_path: Path to the database file. If None, uses config default.
            config_manager: Configuration manager instance.
        """
        from .config_manager import get_default_config_manager
        self._config_manager = config_manager or get_default_config_manager()
        self._db_path = db_path or self._config_manager.get('database', 'path')
        self._lock = threading.RLock()
        self._connection: Optional[sqlite3.Connection] = None
        self._initialized = False
        self.initialize()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create the database connection."""
        if self._connection is None:
            try:
                db_config = self._config_manager.get_database_advanced_config()
                self._connection = sqlite3.connect(
                    self._db_path, 
                    timeout=db_config.get('timeout', 30.0),
                    isolation_level=None
                )
                self._connection.row_factory = sqlite3.Row
                
                self._connection.execute(f"PRAGMA journal_mode={db_config.get('wal_mode', 'WAL')}")
                self._connection.execute(f"PRAGMA synchronous={db_config.get('synchronous_mode', 'NORMAL')}")
                self._connection.execute(f"PRAGMA cache_size={db_config.get('cache_size', 500)}")
                self._connection.execute(f"PRAGMA temp_store={db_config.get('temp_store', 'MEMORY')}")
                
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
            conn.commit()
        except Exception:
            conn.rollback()
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
                self._run_migrations(conn)
                self._initialized = True
                logger.info("Database initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                raise

    def _list_migrations(self):
        """Return a sorted list of (name, sql_text) pairs from the package."""
        pkg = resources.files(__package__).joinpath('migrations')
        items = []
        for entry in pkg.iterdir():
            if entry.name.endswith('.sql'):
                items.append((entry.name, entry.read_text()))
        items.sort(key=lambda pair: pair[0])
        return items

    @staticmethod
    def _split_sql_statements(script: str):
        """Split a SQL script into complete statements, respecting BEGIN/END blocks."""
        buffer = ''
        for line in script.splitlines(keepends=True):
            stripped = line.strip()
            if not stripped or stripped.startswith('--'):
                if buffer:
                    buffer += line
                continue
            buffer += line
            if sqlite3.complete_statement(buffer):
                yield buffer.strip()
                buffer = ''
        leftover = buffer.strip()
        if leftover:
            yield leftover

    def _ensure_migrations_table(self, conn: sqlite3.Connection) -> None:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS migrations (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       migration_name TEXT NOT NULL UNIQUE,
                       applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                   )"""
            )
        finally:
            cursor.close()

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        """Run all pending migrations atomically."""
        self._ensure_migrations_table(conn)

        cursor = conn.cursor()
        try:
            cursor.execute("SELECT migration_name FROM migrations")
            applied = {row['migration_name'] for row in cursor.fetchall()}
        finally:
            cursor.close()

        for name, sql_text in self._list_migrations():
            if name in applied:
                continue
            try:
                with self._transaction() as trans_conn:
                    inner = trans_conn.cursor()
                    try:
                        for statement in self._split_sql_statements(sql_text):
                            inner.execute(statement)
                        inner.execute(
                            "INSERT INTO migrations (migration_name) VALUES (?)",
                            (name,),
                        )
                    finally:
                        inner.close()
                logger.info(f"Applied migration: {name}")
            except Exception as e:
                logger.error(f"Failed to apply migration {name}: {e}")
                raise
    
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
        """Add items to inventory. Raises DatabaseError on storage failure."""
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    current = self.get_current_quantity(item_name)
                    new_quantity = current + quantity
                    
                    if current > 0:
                        cursor.execute(
                            "UPDATE inventory SET quantity = ? WHERE item_name = ?",
                            (new_quantity, item_name)
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO inventory (item_name, quantity) VALUES (?, ?)",
                            (item_name, new_quantity)
                        )
                    
                    cursor.execute(
                        """INSERT INTO inventory_history 
                           (item_name, previous_quantity, new_quantity, operation_type)
                           VALUES (?, ?, ?, 'add')""",
                        (item_name, current, new_quantity)
                    )
                    cursor.close()
                return True
            except sqlite3.Error as e:
                logger.error(f"Database error in add_item({item_name}): {e}")
                raise DatabaseError(str(e)) from e
    
    def remove_item(self, item_name: str, quantity: int) -> bool:
        """Remove items from inventory."""
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    current = self.get_current_quantity(item_name)
                    new_quantity = max(0, current - quantity)
                    
                    if new_quantity == 0:
                        cursor.execute(
                            "DELETE FROM inventory WHERE item_name = ?",
                            (item_name,)
                        )
                    else:
                        cursor.execute(
                            "UPDATE inventory SET quantity = ? WHERE item_name = ?",
                            (new_quantity, item_name)
                        )
                    
                    cursor.execute(
                        """INSERT INTO inventory_history 
                           (item_name, previous_quantity, new_quantity, operation_type)
                           VALUES (?, ?, ?, 'remove')""",
                        (item_name, current, new_quantity)
                    )
                    cursor.close()
                return True
            except sqlite3.Error as e:
                logger.error(f"Database error in remove_item({item_name}): {e}")
                raise DatabaseError(str(e)) from e
    
    def set_item(self, item_name: str, quantity: int) -> bool:
        """Set the quantity of an item."""
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    current = self.get_current_quantity(item_name)
                    
                    if quantity == 0:
                        cursor.execute(
                            "DELETE FROM inventory WHERE item_name = ?",
                            (item_name,)
                        )
                    elif current > 0:
                        cursor.execute(
                            "UPDATE inventory SET quantity = ? WHERE item_name = ?",
                            (quantity, item_name)
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO inventory (item_name, quantity) VALUES (?, ?)",
                            (item_name, quantity)
                        )
                    
                    cursor.execute(
                        """INSERT INTO inventory_history 
                           (item_name, previous_quantity, new_quantity, operation_type)
                           VALUES (?, ?, ?, 'set')""",
                        (item_name, current, quantity)
                    )
                    cursor.close()
                return True
            except sqlite3.Error as e:
                logger.error(f"Database error in set_item({item_name}): {e}")
                raise DatabaseError(str(e)) from e
    
    def undo_last_change(self) -> tuple[bool, Optional[str]]:
        """Undo the last inventory change."""
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """SELECT * FROM inventory_history 
                           ORDER BY id DESC LIMIT 1"""
                    )
                    last_change = cursor.fetchone()
                    
                    if not last_change:
                        return False, None
                    
                    history_id = last_change['id']
                    item_name = last_change['item_name']
                    previous_quantity = last_change['previous_quantity']
                    
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
                    
                    cursor.execute(
                        "DELETE FROM inventory_history WHERE id = ?",
                        (history_id,)
                    )
                    cursor.close()
                return True, item_name
            except sqlite3.Error as e:
                logger.error(f"Database error in undo_last_change: {e}")
                raise DatabaseError(str(e)) from e
    
    def get_inventory(self) -> List[tuple[str, int]]:
        """Get the current inventory state."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT item_name, quantity FROM inventory WHERE quantity > 0 ORDER BY item_name"
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

def create_database_manager(config_manager: Any, db_path: Optional[str] = None) -> DatabaseManager:
    """Create a new database manager instance."""
    return DatabaseManager(db_path=db_path, config_manager=config_manager)


_default_db_manager: Optional[DatabaseManager] = None
_default_db_lock = threading.Lock()


def get_default_db_manager() -> DatabaseManager:
    """Lazily create and return a process-wide default DatabaseManager."""
    global _default_db_manager
    with _default_db_lock:
        if _default_db_manager is None:
            from .config_manager import get_default_config_manager
            _default_db_manager = create_database_manager(get_default_config_manager())
        return _default_db_manager
