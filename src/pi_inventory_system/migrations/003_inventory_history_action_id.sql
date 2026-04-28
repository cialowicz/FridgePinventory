-- Group history rows by user-visible action so undo can revert all rows of
-- an action atomically (today every mutator emits one row, but a future bulk
-- operation would silently leave undo half-applied without this column).
ALTER TABLE inventory_history ADD COLUMN action_id INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_inventory_history_action_id
    ON inventory_history (action_id);
