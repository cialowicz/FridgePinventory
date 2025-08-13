# Module for interacting with SQLite database
# This module now acts as a compatibility layer for the new DatabaseManager

import logging
from typing import List, Optional
from .database_manager import db_manager

logger = logging.getLogger(__name__)


def get_migrations_dir() -> str:
    """Get the path to the migrations directory."""
    return db_manager.get_migrations_dir()


def get_pending_migrations(conn=None) -> List[str]:
    """Get a list of pending migrations that haven't been run yet.
    
    Args:
        conn: Ignored, kept for compatibility
        
    Returns:
        List of migration file paths that need to be run
    """
    return db_manager.get_pending_migrations()


def run_migration(conn, migration_file: str) -> None:
    """Run a single migration file.
    
    Args:
        conn: Ignored, kept for compatibility
        migration_file: Path to the migration file
    """
    db_manager.run_migration(migration_file)


def init_db(db_path: str = None) -> None:
    """Initialize the database with all pending migrations."""
    db_manager.initialize(db_path)


def get_db():
    """Get the database connection."""
    return db_manager.get_connection()


def close_db():
    """Close the database connection."""
    db_manager.close()


def get_current_quantity(item_name: str) -> int:
    """Get the current quantity of an item."""
    return db_manager.get_current_quantity(item_name)


def add_item(item_name: str, quantity: int) -> bool:
    """Add items to inventory."""
    return db_manager.add_item(item_name, quantity)


def remove_item(item_name: str, quantity: int) -> bool:
    """Remove items from inventory."""
    return db_manager.remove_item(item_name, quantity)


def set_item(item_name: str, quantity: int) -> bool:
    """Set the quantity of an item."""
    return db_manager.set_item(item_name, quantity)


def undo_last_change() -> bool:
    """Undo the last inventory change."""
    return db_manager.undo_last_change()


def get_inventory() -> List[tuple]:
    """Get the current inventory state."""
    return db_manager.get_inventory()
