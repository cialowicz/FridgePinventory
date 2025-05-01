# Tests for item normalizer module

import unittest
from src.pi_inventory_system.item_normalizer import normalize_item_name, get_item_synonyms

class TestItemNormalizer(unittest.TestCase):
    def test_basic_normalization(self):
        """Test basic item name normalization."""
        self.assertEqual(normalize_item_name("ground beef"), "ground beef")
        self.assertEqual(normalize_item_name("beef"), "ground beef")
        self.assertEqual(normalize_item_name("ground meat"), "ground beef")

    def test_steak_normalization(self):
        """Test steak variations."""
        self.assertEqual(normalize_item_name("steak"), "steak")
        self.assertEqual(normalize_item_name("steaks"), "steak")
        self.assertEqual(normalize_item_name("sirloin"), "steak")
        self.assertEqual(normalize_item_name("ribeye"), "steak")

    def test_chicken_normalization(self):
        """Test chicken variations."""
        self.assertEqual(normalize_item_name("chicken breast"), "chicken breast")
        self.assertEqual(normalize_item_name("breast"), "chicken breast")
        self.assertEqual(normalize_item_name("chicken tenders"), "chicken tenders")
        self.assertEqual(normalize_item_name("tenders"), "chicken tenders")
        self.assertEqual(normalize_item_name("chicken nuggets"), "chicken nuggets")
        self.assertEqual(normalize_item_name("nuggets"), "chicken nuggets")

    def test_fish_normalization(self):
        """Test fish variations."""
        self.assertEqual(normalize_item_name("white fish"), "white fish")
        self.assertEqual(normalize_item_name("whitefish"), "white fish")
        self.assertEqual(normalize_item_name("white fish fillet"), "white fish")
        self.assertEqual(normalize_item_name("tilapia"), "white fish")
        self.assertEqual(normalize_item_name("salmon"), "salmon")
        self.assertEqual(normalize_item_name("salmon fillet"), "salmon")

    def test_turkey_normalization(self):
        self.assertEqual(normalize_item_name("ground turkey"), "ground turkey")
        self.assertEqual(normalize_item_name("turkey"), "ground turkey")
        self.assertEqual(normalize_item_name("turkey meat"), "ground turkey")

    def test_ice_cream_normalization(self):
        self.assertEqual(normalize_item_name("ice cream"), "ice cream")
        self.assertEqual(normalize_item_name("icecream"), "ice cream")
        self.assertEqual(normalize_item_name("vanilla ice cream"), "ice cream")
        self.assertEqual(normalize_item_name("ice cream tub"), "ice cream")

    def test_get_synonyms(self):
        synonyms = get_item_synonyms("ground beef")
        self.assertIn("beef", synonyms)
        self.assertIn("ground meat", synonyms)
        self.assertIn("ground beef", synonyms)

    def test_unknown_items(self):
        # Unknown items should return as-is
        self.assertEqual(normalize_item_name("unknown item"), "unknown item")
        self.assertEqual(normalize_item_name("random food"), "random food")

if __name__ == '__main__':
    unittest.main() 