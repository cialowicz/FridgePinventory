# SQLite database manager for the Pi application.

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Any, List, Optional

from .constants import MAX_QUANTITY
from .exceptions import DatabaseError, InventoryError
from .inventory_item import InventoryItem

logger = logging.getLogger(__name__)

VALID_JOURNAL_MODES = {'DELETE', 'TRUNCATE', 'PERSIST', 'MEMORY', 'WAL', 'OFF'}
VALID_SYNCHRONOUS_MODES = {'OFF', 'NORMAL', 'FULL', 'EXTRA'}
VALID_TEMP_STORES = {'DEFAULT', 'FILE', 'MEMORY'}


def _safe_pragma_choice(value: Any, allowed: set[str], default: str) -> str:
    choice = str(value).upper()
    if choice not in allowed:
        logger.warning(f"Invalid SQLite PRAGMA value {value!r}; using {default}")
        return default
    return choice


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning(f"Invalid integer config value {value!r}; using {default}")
        return default


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
        raw_path = db_path or self._config_manager.get('database', 'path') or ':memory:'
        self._db_path = self._resolve_db_path(raw_path)
        # check_same_thread=False lets the voice worker use the same connection;
        # every connection access must remain guarded by this re-entrant lock.
        self._lock = threading.RLock()
        self._connection: Optional[sqlite3.Connection] = None
        self._initialized = False
        self.initialize()
    
    @staticmethod
    def _resolve_db_path(raw_path: str) -> str:
        """Expand ~ / env vars and ensure the parent directory exists for file paths."""
        if raw_path == ':memory:':
            return raw_path
        expanded = os.path.expandvars(os.path.expanduser(raw_path))
        parent = Path(expanded).parent
        if str(parent) and parent != Path('') and parent != Path('.'):
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(f"Could not create database directory {parent}: {e}")
        return expanded

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create the database connection."""
        if self._connection is None:
            try:
                db_config = self._config_manager.get_database_advanced_config()
                self._connection = sqlite3.connect(
                    self._db_path, 
                    timeout=db_config.get('timeout', 30.0),
                    isolation_level=None,
                    check_same_thread=False,
                )
                self._connection.row_factory = sqlite3.Row
                
                journal_mode = _safe_pragma_choice(
                    db_config.get('wal_mode', 'WAL'),
                    VALID_JOURNAL_MODES,
                    'WAL',
                )
                synchronous_mode = _safe_pragma_choice(
                    db_config.get('synchronous_mode', 'NORMAL'),
                    VALID_SYNCHRONOUS_MODES,
                    'NORMAL',
                )
                temp_store = _safe_pragma_choice(
                    db_config.get('temp_store', 'MEMORY'),
                    VALID_TEMP_STORES,
                    'MEMORY',
                )
                cache_size = _safe_int(db_config.get('cache_size', 500), 500)
                self._connection.execute(f"PRAGMA journal_mode={journal_mode}")
                self._connection.execute(f"PRAGMA synchronous={synchronous_mode}")
                self._connection.execute(f"PRAGMA cache_size={cache_size}")
                self._connection.execute(f"PRAGMA temp_store={temp_store}")
                
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
        """Get the current quantity of an item. Raises DatabaseError on
        storage failure."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "SELECT quantity FROM inventory WHERE item_name = ?",
                        (item_name,)
                    )
                    result = cursor.fetchone()
                finally:
                    cursor.close()
                return result['quantity'] if result else 0
            except sqlite3.Error as e:
                logger.error(f"Database error in get_current_quantity({item_name}): {e}")
                raise DatabaseError(str(e)) from e

    def _set_inventory_quantity(
        self,
        cursor: sqlite3.Cursor,
        item_name: str,
        quantity: int,
    ) -> None:
        """Set inventory quantity, inserting or deleting the row as needed."""
        if quantity <= 0:
            cursor.execute(
                "DELETE FROM inventory WHERE item_name = ?",
                (item_name,)
            )
            return

        cursor.execute(
            "UPDATE inventory SET quantity = ? WHERE item_name = ?",
            (quantity, item_name)
        )
        if cursor.rowcount == 0:
            cursor.execute(
                "INSERT INTO inventory (item_name, quantity) VALUES (?, ?)",
                (item_name, quantity)
            )

    def _next_action_id(self, cursor: sqlite3.Cursor) -> int:
        """Allocate the next action_id. action_ids are monotonic per process
        and grouped by user-visible action — every history row written inside
        a single mutator call shares the same action_id and is undone together."""
        cursor.execute("SELECT COALESCE(MAX(action_id), 0) FROM inventory_history")
        return int(cursor.fetchone()[0]) + 1

    def _record_history(
        self,
        cursor: sqlite3.Cursor,
        item_name: str,
        previous_quantity: int,
        new_quantity: int,
        operation_type: str,
        action_id: int,
    ) -> None:
        cursor.execute(
            """INSERT INTO inventory_history
               (item_name, previous_quantity, new_quantity, operation_type, action_id)
               VALUES (?, ?, ?, ?, ?)""",
            (item_name, previous_quantity, new_quantity, operation_type, action_id)
        )

    @staticmethod
    def _validate_quantity(quantity: int, *, allow_zero: bool) -> None:
        """Enforce storage-layer quantity invariants for public mutators."""
        if not isinstance(quantity, int):
            raise ValueError("quantity must be an integer")
        if quantity < 0:
            raise ValueError("quantity cannot be negative")
        if quantity == 0 and not allow_zero:
            raise ValueError("quantity must be greater than zero")
        if quantity > MAX_QUANTITY:
            raise ValueError(f"quantity cannot exceed {MAX_QUANTITY}")
    
    def add_item(self, item_name: str, quantity: int) -> bool:
        """Add items to inventory. Raises DatabaseError on storage failure
        and InventoryError when the addition would exceed MAX_QUANTITY."""
        self._validate_quantity(quantity, allow_zero=False)
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    try:
                        current = self.get_current_quantity(item_name)
                        new_quantity = current + quantity
                        if new_quantity > MAX_QUANTITY:
                            # Typed so the controller's InventoryError handler
                            # turns this into spoken feedback, not a generic
                            # "unexpected error".
                            raise InventoryError(
                                f"quantity cannot exceed {MAX_QUANTITY}"
                            )
                        action_id = self._next_action_id(cursor)
                        self._set_inventory_quantity(cursor, item_name, new_quantity)
                        self._record_history(cursor, item_name, current, new_quantity,
                                             'add', action_id)
                    finally:
                        cursor.close()
                return True
            except sqlite3.Error as e:
                logger.error(f"Database error in add_item({item_name}): {e}")
                raise DatabaseError(str(e)) from e
    
    def remove_item(self, item_name: str, quantity: int) -> bool:
        """Remove items from inventory."""
        self._validate_quantity(quantity, allow_zero=False)
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    try:
                        current = self.get_current_quantity(item_name)
                        if current <= 0:
                            return False

                        new_quantity = max(0, current - quantity)
                        action_id = self._next_action_id(cursor)
                        self._set_inventory_quantity(cursor, item_name, new_quantity)
                        self._record_history(cursor, item_name, current, new_quantity,
                                             'remove', action_id)
                    finally:
                        cursor.close()
                return True
            except sqlite3.Error as e:
                logger.error(f"Database error in remove_item({item_name}): {e}")
                raise DatabaseError(str(e)) from e
    
    def set_item(self, item_name: str, quantity: int) -> bool:
        """Set the quantity of an item."""
        self._validate_quantity(quantity, allow_zero=True)
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    try:
                        current = self.get_current_quantity(item_name)
                        action_id = self._next_action_id(cursor)
                        self._set_inventory_quantity(cursor, item_name, quantity)
                        self._record_history(cursor, item_name, current, quantity,
                                             'set', action_id)
                    finally:
                        cursor.close()
                return True
            except sqlite3.Error as e:
                logger.error(f"Database error in set_item({item_name}): {e}")
                raise DatabaseError(str(e)) from e
    
    def undo_last_change(self) -> tuple[bool, Optional[str]]:
        """Undo the most recent action atomically.

        Reverts every history row sharing the latest action_id (today every
        mutator writes one row, but a future bulk operation will write many).
        Returns (True, item_name_of_first_row) on success — the spoken
        confirmation message uses the primary item name.
        """
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute(
                            "SELECT MAX(action_id) FROM inventory_history "
                            "WHERE action_id > 0"
                        )
                        row = cursor.fetchone()
                        latest_action_id = row[0] if row else None

                        if latest_action_id is None or latest_action_id == 0:
                            # Pre-action_id rows (legacy) or empty history:
                            # fall back to single-row undo by id.
                            cursor.execute(
                                "SELECT id, item_name, previous_quantity "
                                "FROM inventory_history ORDER BY id DESC LIMIT 1"
                            )
                            legacy = cursor.fetchone()
                            if not legacy:
                                return False, None
                            self._set_inventory_quantity(
                                cursor, legacy['item_name'], legacy['previous_quantity'])
                            cursor.execute(
                                "DELETE FROM inventory_history WHERE id = ?",
                                (legacy['id'],),
                            )
                            return True, legacy['item_name']

                        cursor.execute(
                            "SELECT id, item_name, previous_quantity "
                            "FROM inventory_history WHERE action_id = ? "
                            "ORDER BY id ASC",
                            (latest_action_id,),
                        )
                        rows = cursor.fetchall()
                        if not rows:
                            return False, None

                        # Revert in reverse insertion order so dependent
                        # writes within the action unwind cleanly.
                        for row in reversed(rows):
                            self._set_inventory_quantity(
                                cursor, row['item_name'], row['previous_quantity'])

                        cursor.execute(
                            "DELETE FROM inventory_history WHERE action_id = ?",
                            (latest_action_id,),
                        )
                        return True, rows[0]['item_name']
                    finally:
                        cursor.close()
            except sqlite3.Error as e:
                logger.error(f"Database error in undo_last_change: {e}")
                raise DatabaseError(str(e)) from e
    
    def get_inventory(self) -> List[tuple[str, int]]:
        """Get the current inventory state. Raises DatabaseError on storage
        failure."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "SELECT item_name, quantity FROM inventory "
                        "WHERE quantity > 0 ORDER BY item_name"
                    )
                    result = [
                        (row['item_name'], row['quantity'])
                        for row in cursor.fetchall()
                    ]
                finally:
                    cursor.close()
                return result
            except sqlite3.Error as e:
                logger.error(f"Database error in get_inventory: {e}")
                raise DatabaseError(str(e)) from e
    
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
