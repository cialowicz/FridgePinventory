import pytest

from pi_inventory_system.inventory_item import InventoryItem


def test_inventory_item_rejects_invalid_fields():
    with pytest.raises(ValueError):
        InventoryItem(item_name=123, quantity=1)
    with pytest.raises(ValueError):
        InventoryItem(item_name="salmon", quantity="1")
    with pytest.raises(ValueError):
        InventoryItem(item_name="salmon", quantity=-1)


def test_inventory_item_tuple_helpers():
    item = InventoryItem.from_tuple(("salmon", "3"))
    assert item == InventoryItem(item_name="salmon", quantity=3)
    assert item.to_tuple() == ("salmon", 3)
    with pytest.raises(ValueError):
        InventoryItem.from_tuple(("salmon", 3, "extra"))
