# Module for interacting with SQLite database

import sqlite3
import os
import glob
from typing import List, Optional
from datetime import datetime
from pi_inventory_system.inventory_item import InventoryItem


# Global database connection
_db_connection = None


def get_migrations_dir() -> str:
    """Get the path to the migrations directory."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    return os.path.join(project_root, 'migrations')


def get_pending_migrations(conn) -> List[str]:
    """Get a list of migration files that haven't been run yet."""
    cursor = conn.cursor()
    
    # Create migrations table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_name TEXT NOT NULL UNIQUE,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    
    # Get all migration files
    migrations_dir = get_migrations_dir()
    migration_files = sorted(glob.glob(os.path.join(migrations_dir, '*.sql')))
    
    # Get already applied migrations
    cursor.execute("SELECT migration_name FROM migrations")
    applied_migrations = {row[0] for row in cursor.fetchall()}
    
    # Return only pending migrations
    pending = []
    for migration_file in migration_files:
        migration_name = os.path.basename(migration_file)
        if migration_name not in applied_migrations:
            pending.append(migration_file)
    
    return pending


def run_migration(conn, migration_file: str) -> None:
    """Run a single migration file."""
    cursor = conn.cursor()
    migration_name = os.path.basename(migration_file)
    
    try:
        # Read and execute the migration file
        with open(migration_file, 'r') as f:
            sql = f.read()
            cursor.executescript(sql)
        
        # Record the migration as applied
        cursor.execute(
            "INSERT INTO migrations (migration_name) VALUES (?)",
            (migration_name,)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e


def init_db(db_path: str = ':memory:') -> None:
    """Initialize the database with all pending migrations."""
    global _db_connection
    
    if _db_connection is not None:
        return
    
    try:
        _db_connection = sqlite3.connect(db_path)
        _db_connection.row_factory = sqlite3.Row
        
        # Run all pending migrations
        pending_migrations = get_pending_migrations(_db_connection)
        for migration_file in pending_migrations:
            run_migration(_db_connection, migration_file)
            
    except Exception as e:
        if _db_connection:
            _db_connection.close()
            _db_connection = None
        raise e


def get_db():
    """Get the database connection."""
    if _db_connection is None:
        init_db()
    return _db_connection


def close_db():
    """Close the database connection."""
    global _db_connection
    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None


def get_current_quantity(item_name: str) -> int:
    """Get the current quantity of an item."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT quantity FROM inventory WHERE item_name = ?",
        (item_name,)
    )
    result = cursor.fetchone()
    return result[0] if result else 0


def add_item(item_name: str, quantity: int) -> bool:
    """Add items to inventory."""
    try:
        item = InventoryItem(item_name=item_name, quantity=quantity)
    except ValueError:
        return False
        
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN")
        
        # Get current quantity
        current = get_current_quantity(item.item_name)
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
        
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False


def remove_item(item_name: str, quantity: int) -> bool:
    """Remove items from inventory."""
    try:
        item = InventoryItem(item_name=item_name, quantity=quantity)
    except ValueError:
        return False
        
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN")
        
        # Get current quantity
        current = get_current_quantity(item.item_name)
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
        
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False


def set_item(item_name: str, quantity: int) -> bool:
    """Set the quantity of an item."""
    try:
        item = InventoryItem(item_name=item_name, quantity=quantity)
    except ValueError:
        return False
        
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN")
        
        # Get current quantity
        current = get_current_quantity(item.item_name)
        
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
        
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False


def undo_last_change() -> bool:
    """Undo the last inventory change."""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN")
        
        # Get the last change
        cursor.execute(
            """SELECT * FROM inventory_history 
               ORDER BY id DESC LIMIT 1"""
        )
        last_change = cursor.fetchone()
        
        if not last_change:
            conn.rollback()
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
        
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False


def get_inventory() -> List[tuple]:
    """Get the current inventory state."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT item_name, quantity FROM inventory")
    return [(row['item_name'], row['quantity']) for row in cursor.fetchall()]
