# Tests for item normalizer

import pytest
from unittest.mock import MagicMock
from pi_inventory_system.item_normalizer import normalize_item_name, get_item_synonyms

@pytest.fixture
def mock_config_manager():
    """Mock the config manager."""
    config_manager = MagicMock()
    config_manager.get_command_config.return_value = {'similarity_threshold': 0.8}
    return config_manager

def test_basic_normalization(mock_config_manager):
    """Test basic item name normalization."""
    assert normalize_item_name("ground beef", mock_config_manager) == "ground beef"
    assert normalize_item_name("beef", mock_config_manager) == "ground beef"
    assert normalize_item_name("ground meat", mock_config_manager) == "ground beef"

def test_steak_normalization(mock_config_manager):
    """Test steak variations."""
    assert normalize_item_name("steak", mock_config_manager) == "steak"
    assert normalize_item_name("steaks", mock_config_manager) == "steak"
    assert normalize_item_name("sirloin", mock_config_manager) == "steak"
    assert normalize_item_name("ribeye", mock_config_manager) == "steak"

def test_chicken_normalization(mock_config_manager):
    """Test chicken variations."""
    assert normalize_item_name("chicken breast", mock_config_manager) == "chicken breast"
    assert normalize_item_name("breast", mock_config_manager) == "chicken breast"
    assert normalize_item_name("chicken tenders", mock_config_manager) == "chicken tenders"
    assert normalize_item_name("tenders", mock_config_manager) == "chicken tenders"
    assert normalize_item_name("chicken nuggets", mock_config_manager) == "chicken nuggets"
    assert normalize_item_name("nuggets", mock_config_manager) == "chicken nuggets"

def test_fish_normalization(mock_config_manager):
    """Test fish variations."""
    assert normalize_item_name("white fish", mock_config_manager) == "white fish"
    assert normalize_item_name("whitefish", mock_config_manager) == "white fish"
    assert normalize_item_name("white fish fillet", mock_config_manager) == "white fish"
    assert normalize_item_name("tilapia", mock_config_manager) == "white fish"
    assert normalize_item_name("salmon", mock_config_manager) == "salmon"
    assert normalize_item_name("salmon fillet", mock_config_manager) == "salmon"

def test_turkey_normalization(mock_config_manager):
    assert normalize_item_name("ground turkey", mock_config_manager) == "ground turkey"
    assert normalize_item_name("turkey", mock_config_manager) == "ground turkey"
    assert normalize_item_name("turkey meat", mock_config_manager) == "ground turkey"

def test_ice_cream_normalization(mock_config_manager):
    assert normalize_item_name("ice cream", mock_config_manager) == "ice cream"
    assert normalize_item_name("icecream", mock_config_manager) == "ice cream"
    assert normalize_item_name("vanilla ice cream", mock_config_manager) == "ice cream"
    assert normalize_item_name("ice cream tub", mock_config_manager) == "ice cream"

def test_get_synonyms(mock_config_manager):
    synonyms = get_item_synonyms("ground beef", mock_config_manager)
    assert "beef" in synonyms
    assert "ground meat" in synonyms
    assert "ground beef" in synonyms

def test_unknown_items(mock_config_manager):
    # Unknown items should return as-is
    assert normalize_item_name("unknown item", mock_config_manager) == "unknown item"
    assert normalize_item_name("random food", mock_config_manager) == "random food"
