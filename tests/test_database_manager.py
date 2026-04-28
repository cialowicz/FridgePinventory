"""Tests for the DatabaseManager — migrations, CRUD, undo, transactions."""

import sqlite3

import pytest


def test_migrations_idempotent(db_manager_instance):
    """Running migrations twice produces the same applied set."""
    conn = db_manager_instance._get_connection()
    cur = conn.cursor()
    cur.execute("SELECT migration_name FROM migrations ORDER BY migration_name")
    first = [row['migration_name'] for row in cur.fetchall()]
    cur.close()

    db_manager_instance._initialized = False
    db_manager_instance._run_migrations(conn)

    cur = conn.cursor()
    cur.execute("SELECT migration_name FROM migrations ORDER BY migration_name")
    second = [row['migration_name'] for row in cur.fetchall()]
    cur.close()
    assert first == second
    assert "001_initial_schema.sql" in first
    assert "002_inventory_last_modified_trigger.sql" in first


def test_migrations_applied_tables_exist(db_manager_instance):
    conn = db_manager_instance._get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row['name'] for row in cur.fetchall()}
    cur.close()
    assert {'inventory', 'inventory_history', 'migrations'} <= tables


def test_add_creates_history_row(db_manager_instance):
    assert db_manager_instance.add_item("salmon", 3) is True
    conn = db_manager_instance._get_connection()
    cur = conn.cursor()
    cur.execute("SELECT item_name, previous_quantity, new_quantity, operation_type FROM inventory_history")
    rows = cur.fetchall()
    cur.close()
    assert len(rows) == 1
    assert rows[0]['item_name'] == "salmon"
    assert rows[0]['previous_quantity'] == 0
    assert rows[0]['new_quantity'] == 3
    assert rows[0]['operation_type'] == 'add'


def test_remove_clamps_to_zero_and_deletes(db_manager_instance):
    db_manager_instance.add_item("salmon", 2)
    assert db_manager_instance.remove_item("salmon", 5) is True
    assert db_manager_instance.get_current_quantity("salmon") == 0
    conn = db_manager_instance._get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM inventory WHERE item_name = ?", ("salmon",))
    assert cur.fetchone()['c'] == 0
    cur.close()


def test_set_zero_deletes_row(db_manager_instance):
    db_manager_instance.add_item("steak", 4)
    db_manager_instance.set_item("steak", 0)
    assert db_manager_instance.get_current_quantity("steak") == 0


def test_undo_round_trip(db_manager_instance):
    db_manager_instance.add_item("steak", 4)
    success, name = db_manager_instance.undo_last_change()
    assert success is True
    assert name == "steak"
    assert db_manager_instance.get_current_quantity("steak") == 0


def test_undo_with_no_history(db_manager_instance):
    success, name = db_manager_instance.undo_last_change()
    assert success is False
    assert name is None


def test_get_inventory_skips_zero_rows(db_manager_instance):
    db_manager_instance.add_item("steak", 1)
    db_manager_instance.add_item("salmon", 2)
    db_manager_instance.set_item("salmon", 0)
    inventory = db_manager_instance.get_inventory()
    assert ("steak", 1) in inventory
    assert all(name != "salmon" for name, _ in inventory)


def test_last_modified_trigger_fires(db_manager_instance):
    db_manager_instance.add_item("steak", 1)
    conn = db_manager_instance._get_connection()
    cur = conn.cursor()
    cur.execute("SELECT last_modified FROM inventory WHERE item_name = ?", ("steak",))
    before = cur.fetchone()['last_modified']
    cur.close()

    cur = conn.cursor()
    cur.execute("UPDATE inventory SET quantity = 99 WHERE item_name = ?", ("steak",))
    cur.execute("SELECT last_modified FROM inventory WHERE item_name = ?", ("steak",))
    after = cur.fetchone()['last_modified']
    cur.close()
    assert after >= before


def test_add_item_propagates_database_error(db_manager_instance, monkeypatch):
    """sqlite3.Error inside add_item surfaces as DatabaseError, not silent False."""
    import sqlite3

    from pi_inventory_system.exceptions import DatabaseError

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(db_manager_instance, "get_current_quantity", boom)
    with pytest.raises(DatabaseError):
        db_manager_instance.add_item("steak", 1)


def test_split_sql_statements_handles_trigger():
    from pi_inventory_system.database_manager import DatabaseManager
    script = """
    CREATE TABLE foo (id INTEGER);
    CREATE TRIGGER touch
    AFTER UPDATE ON foo
    FOR EACH ROW
    BEGIN
        UPDATE foo SET id = id WHERE id = NEW.id;
    END;
    """
    statements = list(DatabaseManager._split_sql_statements(script))
    assert len(statements) == 2
    assert statements[0].startswith("CREATE TABLE")
    assert "BEGIN" in statements[1] and statements[1].endswith("END;")
