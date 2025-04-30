# Tests for display manager module

import pytest
from unittest.mock import patch, MagicMock
from pi_inventory_system.display_manager import (
    initialize_display,
    display_inventory,
    is_display_supported,
    InkyWHAT,
    Image,
    ImageDraw,
    ImageFont,
    _is_raspberry_pi
)

@pytest.fixture
def mock_platform():
    with patch('pi_inventory_system.display_manager._is_raspberry_pi') as mock_is_raspberry_pi:
        mock_is_raspberry_pi.return_value = True
        yield mock_is_raspberry_pi

@pytest.fixture
def mock_inky():
    with patch('pi_inventory_system.display_manager.InkyWHAT') as mock_inky:
        mock_instance = MagicMock(spec=InkyWHAT)
        mock_instance.color = 'yellow'
        mock_inky.return_value = mock_instance
        yield mock_inky

def test_is_display_supported(mock_platform):
    """Test display support detection."""
    assert is_display_supported() is True

def test_initialize_display(mock_platform, mock_inky):
    """Test display initialization."""
    display = initialize_display()
    assert isinstance(display, InkyWHAT)
    assert display.color == 'yellow'

def test_display_inventory(mock_platform, mock_inky):
    """Test inventory display."""
    # Create a mock display
    display = MagicMock(spec=InkyWHAT)
    display.WIDTH = 400
    display.HEIGHT = 300
    
    # Mock the inventory data
    with patch('pi_inventory_system.display_manager.get_inventory') as mock_get_inventory:
        mock_get_inventory.return_value = [
            MagicMock(item_name='Test Item 1', quantity=5),
            MagicMock(item_name='Test Item 2', quantity=3)
        ]
        
        # Mock PIL components
        with patch('pi_inventory_system.display_manager.Image') as mock_image, \
             patch('pi_inventory_system.display_manager.ImageDraw') as mock_draw, \
             patch('pi_inventory_system.display_manager.ImageFont') as mock_font:
            
            # Setup mock font
            mock_font_instance = MagicMock()
            mock_font.truetype.return_value = mock_font_instance
            
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

def test_display_inventory_no_display(mock_platform):
    """Test inventory display when no display is available."""
    result = display_inventory(None)
    assert result is None

def test_initialize_display_no_raspberry_pi():
    """Test display initialization on non-Raspberry Pi."""
    with patch('pi_inventory_system.display_manager._is_raspberry_pi') as mock_is_raspberry_pi:
        mock_is_raspberry_pi.return_value = False
        
        display = initialize_display()
        assert display is None
