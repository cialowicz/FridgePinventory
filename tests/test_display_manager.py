# Tests for display manager module

import pytest
from unittest.mock import patch, MagicMock
import pi_inventory_system.display_manager

def test_is_display_supported(mock_raspberry_pi):
    """Test display support detection."""
    assert pi_inventory_system.display_manager.is_display_supported()

    mock_raspberry_pi.return_value = False
    assert not pi_inventory_system.display_manager.is_display_supported()

def test_initialize_display(mock_raspberry_pi): 
    """Test display initialization."""
    # The mock_raspberry_pi fixture ensures that display_manager.py loads as if on a Pi
    # and 'pi_inventory_system.display_manager.auto_inky_display' is already a MagicMock
    # (specifically, mock_inky_auto_import_source from the fixture).
    # We patch it again here to control its behavior for this specific test.
    with patch('pi_inventory_system.display_manager.auto_inky_display') as mock_auto_inky_call_in_test:
        mock_display_object = MagicMock(name="mock_returned_display_object")
        # Mock attributes/methods expected to be used on the display object by initialize_display()
        mock_display_object.WHITE = "mock_white_color" # Simulate display.WHITE
        mock_display_object.set_border = MagicMock()
        mock_display_object.show = MagicMock()

        mock_auto_inky_call_in_test.return_value = mock_display_object

        display = pi_inventory_system.display_manager.initialize_display()

        assert display is mock_display_object
        mock_auto_inky_call_in_test.assert_called_once_with(verbose=True)
        mock_display_object.set_border.assert_called_once_with(mock_display_object.WHITE)
        mock_display_object.show.assert_called_once()

def test_display_inventory(mock_raspberry_pi, mock_display):
    """Test inventory display."""
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
            mock_font.load_default.return_value = mock_font_instance
            
            # Setup mock image
            mock_img = MagicMock()
            mock_image.new.return_value = mock_img
            
            # Setup mock draw
            mock_draw_instance = MagicMock()
            mock_draw.Draw.return_value = mock_draw_instance
            
            # Call the function
            result = pi_inventory_system.display_manager.display_inventory(mock_display)
            
            # Verify the display was updated
            mock_display.set_image.assert_called_once()
            mock_display.show.assert_called_once()
            assert result is True

def test_display_inventory_no_display(mock_raspberry_pi):
    """Test inventory display when no display is available."""
    result = pi_inventory_system.display_manager.display_inventory(None)
    assert result is None

def test_initialize_display_no_raspberry_pi(mock_raspberry_pi):
    """Test display initialization on non-Raspberry Pi."""
    mock_raspberry_pi.return_value = False
    display = pi_inventory_system.display_manager.initialize_display()
    assert display is None

def test_lozenge_border_color(mock_raspberry_pi):
    """Test lozenge border color changes based on quantity."""
    # Mock draw object
    mock_draw = MagicMock()
    mock_font = MagicMock()
    
    # Test with quantity > 2 (should use black border)
    pi_inventory_system.display_manager.create_lozenge(mock_draw, 0, 0, 100, 50, "Test Item", 3, mock_font)
    mock_draw.rectangle.assert_called_with([(0, 0), (100, 50)], fill='white', outline='black')
    
    # Reset mock for next test
    mock_draw.reset_mock()
    
    # Test with quantity = 2 (should use yellow border)
    pi_inventory_system.display_manager.create_lozenge(mock_draw, 0, 0, 100, 50, "Test Item", 2, mock_font)
    mock_draw.rectangle.assert_called_with([(0, 0), (100, 50)], fill='white', outline='yellow')
    
    # Reset mock for next test
    mock_draw.reset_mock()
    
    # Test with quantity < 2 (should use yellow border)
    pi_inventory_system.display_manager.create_lozenge(mock_draw, 0, 0, 100, 50, "Test Item", 1, mock_font)
    mock_draw.rectangle.assert_called_with([(0, 0), (100, 50)], fill='white', outline='yellow')
