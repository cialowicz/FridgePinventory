-- Enforce storage-layer quantity limits for direct SQL writes as well as
-- DatabaseManager calls.
CREATE TRIGGER IF NOT EXISTS inventory_quantity_valid_insert
BEFORE INSERT ON inventory
WHEN NEW.quantity < 0 OR NEW.quantity > 10000
BEGIN
    SELECT RAISE(ABORT, 'inventory quantity out of range');
END;

CREATE TRIGGER IF NOT EXISTS inventory_quantity_valid_update
BEFORE UPDATE OF quantity ON inventory
WHEN NEW.quantity < 0 OR NEW.quantity > 10000
BEGIN
    SELECT RAISE(ABORT, 'inventory quantity out of range');
END;

CREATE TRIGGER IF NOT EXISTS inventory_history_quantity_valid_insert
BEFORE INSERT ON inventory_history
WHEN NEW.previous_quantity < 0
   OR NEW.previous_quantity > 10000
   OR NEW.new_quantity < 0
   OR NEW.new_quantity > 10000
BEGIN
    SELECT RAISE(ABORT, 'inventory history quantity out of range');
END;
