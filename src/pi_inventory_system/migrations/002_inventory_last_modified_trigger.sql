-- Keep inventory.last_modified in sync on UPDATE.
CREATE TRIGGER IF NOT EXISTS inventory_touch_last_modified
AFTER UPDATE OF quantity ON inventory
FOR EACH ROW
BEGIN
    UPDATE inventory SET last_modified = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
