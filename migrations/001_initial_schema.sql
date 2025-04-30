-- Initial schema for the inventory database
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT NOT NULL UNIQUE,
    quantity INTEGER NOT NULL DEFAULT 0
);

-- Table to store history of changes for undo functionality
CREATE TABLE IF NOT EXISTS inventory_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT NOT NULL,
    previous_quantity INTEGER NOT NULL,
    new_quantity INTEGER NOT NULL,
    operation_type TEXT NOT NULL,  -- 'add', 'remove', or 'set'
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
