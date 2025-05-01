# Tests for item normalizer module

import pytest
from pi_inventory_system.item_normalizer import normalize_item_name, get_item_synonyms

def test_basic_normalization():
    """Test basic item name normalization."""
    assert normalize_item_name("ground beef") == "ground beef"
    assert normalize_item_name("beef") == "ground beef"
    assert normalize_item_name("ground meat") == "ground beef"

def test_steak_normalization():
    """Test steak variations."""
    assert normalize_item_name("steak") == "steak"
    assert normalize_item_name("steaks") == "steak"
    assert normalize_item_name("sirloin") == "steak"
    assert normalize_item_name("ribeye") == "steak"

def test_chicken_normalization():
    """Test chicken variations."""
    assert normalize_item_name("chicken breast") == "chicken breast"
    assert normalize_item_name("breast") == "chicken breast"
    assert normalize_item_name("chicken tenders") == "chicken tenders"
    assert normalize_item_name("tenders") == "chicken tenders"
    assert normalize_item_name("chicken nuggets") == "chicken nuggets"
    assert normalize_item_name("nuggets") == "chicken nuggets"

def test_fish_normalization():
    """Test fish variations."""
    assert normalize_item_name("white fish") == "white fish"
    assert normalize_item_name("whitefish") == "white fish"
    assert normalize_item_name("white fish fillet") == "white fish"
    assert normalize_item_name("tilapia") == "white fish"
    assert normalize_item_name("salmon") == "salmon"
    assert normalize_item_name("salmon fillet") == "salmon"

def test_turkey_normalization():
    assert normalize_item_name("ground turkey") == "ground turkey"
    assert normalize_item_name("turkey") == "ground turkey"
    assert normalize_item_name("turkey meat") == "ground turkey"

def test_ice_cream_normalization():
    assert normalize_item_name("ice cream") == "ice cream"
    assert normalize_item_name("icecream") == "ice cream"
    assert normalize_item_name("vanilla ice cream") == "ice cream"
    assert normalize_item_name("ice cream tub") == "ice cream"

def test_get_synonyms():
    synonyms = get_item_synonyms("ground beef")
    assert "beef" in synonyms
    assert "ground meat" in synonyms
    assert "ground beef" in synonyms

def test_unknown_items():
    # Unknown items should return as-is
    assert normalize_item_name("unknown item") == "unknown item"
    assert normalize_item_name("random food") == "random food" 