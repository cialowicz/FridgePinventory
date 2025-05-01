# Tests for display manager module

import unittest
from unittest.mock import patch, MagicMock
from src.pi_inventory_system.display_manager import (
    initialize_display,
    display_inventory,
    is_display_supported,
    InkyWHAT,
    Image,
    ImageDraw,
    ImageFont,
    _is_raspberry_pi
)
import pytest

@pytest.fixture
def mock_platform():
    with patch('src.pi_inventory_system.motion_sensor._is_raspberry_pi') as mock_is_raspberry_pi:
        mock_is_raspberry_pi.return_value = True
        yield mock_is_raspberry_pi

@pytest.fixture
def mock_inky():
    with patch('src.pi_inventory_system.display_manager.InkyWHAT') as mock_inky:
        mock_instance = MagicMock()
        mock_instance.color = 'yellow'
        mock_instance.WIDTH = 400
        mock_instance.HEIGHT = 300
        mock_inky.return_value = mock_instance
        yield mock_inky

def test_is_display_supported():
    """Test display support detection."""
    with patch('src.pi_inventory_system.display_manager._is_raspberry_pi') as mock_is_raspberry_pi:
        mock_is_raspberry_pi.return_value = True
        assert is_display_supported() is True

def test_initialize_display():
    """Test display initialization."""
    with patch('src.pi_inventory_system.display_manager._is_raspberry_pi') as mock_is_raspberry_pi:
        mock_is_raspberry_pi.return_value = True
        with patch('src.pi_inventory_system.display_manager.InkyWHAT') as mock_inky:
            mock_instance = MagicMock()
            mock_instance.color = 'yellow'
            mock_inky.return_value = mock_instance
            display = initialize_display()
            assert isinstance(display, MagicMock)
            assert display.color == 'yellow'

def test_display_inventory():
    """Test inventory display."""
    with patch('src.pi_inventory_system.display_manager._is_raspberry_pi') as mock_is_raspberry_pi:
        mock_is_raspberry_pi.return_value = True
        
        # Create a mock display
        display = MagicMock()
        display.WIDTH = 400
        display.HEIGHT = 300
        
        # Mock the inventory data
        with patch('src.pi_inventory_system.display_manager.get_inventory') as mock_get_inventory:
            mock_get_inventory.return_value = [
                MagicMock(item_name='Test Item 1', quantity=5),
                MagicMock(item_name='Test Item 2', quantity=3)
            ]
            
            # Mock PIL components
            with patch('src.pi_inventory_system.display_manager.Image') as mock_image, \
                 patch('src.pi_inventory_system.display_manager.ImageDraw') as mock_draw, \
                 patch('src.pi_inventory_system.display_manager.ImageFont') as mock_font:
                
                # Setup mock font
                mock_font_instance = MagicMock()
                mock_font.truetype.return_value = mock_font_instance
                mock_font.load_default.return_value = mock_font_instance
                
                # Setup mock image
                mock_img = MagicMock()
                mock_image.new.return_value = mock_img
                
                # Setup mock draw
                mock_draw_instance = MagicMock()
                mock_draw.Draw.return_value = mock_draw_instance
                
                # Call the function
                result = display_inventory(display)
                
                # Verify the display was updated
                display.set_image.assert_called_once()
                display.show.assert_called_once()
                assert result is True

def test_display_inventory_no_display():
    """Test inventory display when no display is available."""
    result = display_inventory(None)
    assert result is None

def test_initialize_display_no_raspberry_pi():
    """Test display initialization on non-Raspberry Pi."""
    with patch('src.pi_inventory_system.display_manager._is_raspberry_pi') as mock_is_raspberry_pi:
        mock_is_raspberry_pi.return_value = False
        display = initialize_display()
        assert display is None

class TestDisplayManager(unittest.TestCase):
    """Test cases for display manager functionality."""

    def setUp(self):
        """Set up test environment."""
        self.platform_patcher = patch('src.pi_inventory_system.display_manager._is_raspberry_pi')
        self.mock_is_raspberry_pi = self.platform_patcher.start()
        self.mock_is_raspberry_pi.return_value = True

    def tearDown(self):
        """Clean up test environment."""
        self.platform_patcher.stop()

    def test_is_display_supported(self):
        """Test display support detection."""
        self.assertTrue(is_display_supported())

        self.mock_is_raspberry_pi.return_value = False
        self.assertFalse(is_display_supported())

    def test_initialize_display(self):
        """Test display initialization."""
        with patch('src.pi_inventory_system.display_manager.InkyWHAT') as mock_inky:
            mock_instance = MagicMock()
            mock_instance.color = 'yellow'
            mock_inky.return_value = mock_instance
            display = initialize_display()
            self.assertIsInstance(display, MagicMock)
            self.assertEqual(display.color, 'yellow')

    def test_display_inventory(self):
        """Test inventory display."""
        # Create a mock display
        display = MagicMock()
        display.WIDTH = 400
        display.HEIGHT = 300
        
        # Mock the inventory data
        with patch('src.pi_inventory_system.display_manager.get_inventory') as mock_get_inventory:
            mock_get_inventory.return_value = [
                MagicMock(item_name='Test Item 1', quantity=5),
                MagicMock(item_name='Test Item 2', quantity=3)
            ]
            
            # Mock PIL components
            with patch('src.pi_inventory_system.display_manager.Image') as mock_image, \
                 patch('src.pi_inventory_system.display_manager.ImageDraw') as mock_draw, \
                 patch('src.pi_inventory_system.display_manager.ImageFont') as mock_font:
                
                # Setup mock font
                mock_font_instance = MagicMock()
                mock_font.truetype.return_value = mock_font_instance
                mock_font.load_default.return_value = mock_font_instance
                
                # Setup mock image
                mock_img = MagicMock()
                mock_image.new.return_value = mock_img
                
                # Setup mock draw
                mock_draw_instance = MagicMock()
                mock_draw.Draw.return_value = mock_draw_instance
                
                # Call the function
                result = display_inventory(display)
                
                # Verify the display was updated
                display.set_image.assert_called_once()
                display.show.assert_called_once()
                self.assertTrue(result)

    def test_display_inventory_no_display(self):
        """Test inventory display when no display is available."""
        result = display_inventory(None)
        self.assertIsNone(result)

    def test_initialize_display_no_raspberry_pi(self):
        """Test display initialization on non-Raspberry Pi."""
        self.mock_is_raspberry_pi.return_value = False
        display = initialize_display()
        self.assertIsNone(display)


if __name__ == '__main__':
    unittest.main()
