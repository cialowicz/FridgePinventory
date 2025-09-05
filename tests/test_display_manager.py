# Tests for display manager module

import pytest
from unittest.mock import patch, MagicMock, Mock
import pi_inventory_system.display_manager

def test_is_display_supported(mock_raspberry_pi):
    """Test display support detection."""
    # Patch the module-level is_raspberry_pi variable
    with patch('pi_inventory_system.display_manager.is_raspberry_pi', True):
        assert pi_inventory_system.display_manager.is_display_supported()
    
    with patch('pi_inventory_system.display_manager.is_raspberry_pi', False):
        assert not pi_inventory_system.display_manager.is_display_supported()

def test_initialize_display(mock_raspberry_pi): 
    """Test display initialization."""
    with patch('pi_inventory_system.display_manager.is_raspberry_pi', True), \
         patch('pi_inventory_system.display_manager.WaveshareDisplay') as mock_waveshare_class:
        mock_display_instance = MagicMock(name="mock_waveshare_display")
        mock_display_instance.initialize.return_value = True
        mock_display_instance.WIDTH = 800
        mock_display_instance.HEIGHT = 480
        mock_waveshare_class.return_value = mock_display_instance

        display = pi_inventory_system.display_manager.initialize_display()

        assert display is mock_display_instance
        mock_waveshare_class.assert_called_once()
        mock_display_instance.initialize.assert_called_once()

def test_display_inventory(mock_raspberry_pi):
    """Test inventory display."""
    # Create a mock display with Waveshare properties
    mock_display = MagicMock()
    mock_display.WIDTH = 800
    mock_display.HEIGHT = 480
    mock_display.display_image = MagicMock()
    
    # Mock the inventory data as tuples (item_name, quantity)
    inventory = [
        ('Test Item 1', 5),
        ('Test Item 2', 3)
    ]
    
    # Mock PIL components
    with patch('pi_inventory_system.display_manager.Image') as mock_image, \
         patch('pi_inventory_system.display_manager.ImageDraw') as mock_draw, \
         patch('pi_inventory_system.display_manager.ImageFont') as mock_font:
        
        # Setup mock font with size attribute
        mock_font_instance = MagicMock()
        mock_font_instance.size = 18
        mock_font.truetype.return_value = mock_font_instance
        mock_font.load_default.return_value = mock_font_instance
        
        # Setup mock image
        mock_img = MagicMock()
        mock_image.new.return_value = mock_img
        
        # Setup mock draw with textbbox and rounded_rectangle
        mock_draw_instance = MagicMock()
        mock_draw_instance.textbbox.return_value = (0, 0, 100, 20)  # Mock text boundaries
        mock_draw_instance.rounded_rectangle = MagicMock()
        mock_draw.Draw.return_value = mock_draw_instance
        
        # Call the function
        result = pi_inventory_system.display_manager.display_inventory(mock_display, inventory)
        
        # Verify the display was updated
        mock_display.display_image.assert_called_once()
        assert result is True

def test_display_inventory_no_display(mock_raspberry_pi):
    """Test inventory display when no display is available."""
    result = pi_inventory_system.display_manager.display_inventory(None, [])
    assert result is False

def test_initialize_display_no_raspberry_pi(mock_raspberry_pi):
    """Test display initialization on non-Raspberry Pi."""
    mock_raspberry_pi.return_value = False
    display = pi_inventory_system.display_manager.initialize_display()
    assert display is None

def test_display_text(mock_raspberry_pi):
    """Test text display on Waveshare display."""
    # Create a mock display with Waveshare properties
    mock_display = MagicMock()
    mock_display.WIDTH = 800
    mock_display.HEIGHT = 480
    mock_display.display_image = MagicMock()
    
    # Mock PIL components
    with patch('pi_inventory_system.display_manager.Image') as mock_image, \
         patch('pi_inventory_system.display_manager.ImageDraw') as mock_draw, \
         patch('pi_inventory_system.display_manager.ImageFont') as mock_font:
        
        # Setup mock font with size attribute
        mock_font_instance = MagicMock()
        mock_font_instance.size = 24
        mock_font.truetype.return_value = mock_font_instance
        mock_font.load_default.return_value = mock_font_instance
        
        # Setup mock image
        mock_img = MagicMock()
        mock_image.new.return_value = mock_img
        
        # Setup mock draw with textbbox
        mock_draw_instance = MagicMock()
        mock_draw_instance.textbbox.return_value = (0, 0, 200, 30)  # Mock text boundaries
        mock_draw_instance.text = MagicMock()
        mock_draw.Draw.return_value = mock_draw_instance
        
        # Call the function
        result = pi_inventory_system.display_manager.display_text(mock_display, "Test Message", 24)
        
        # Verify the display was updated
        mock_display.display_image.assert_called_once()
        assert result is True

def test_display_text_no_display(mock_raspberry_pi):
    """Test text display when no display is available."""
    result = pi_inventory_system.display_manager.display_text(None, "Test Message")
    assert result is False

def test_lozenge_border_color(mock_raspberry_pi):
    """Test lozenge border color changes based on quantity."""
    # Mock draw object with rounded_rectangle method
    mock_draw = MagicMock()
    mock_draw.rounded_rectangle = MagicMock()
    mock_draw.textbbox.return_value = (0, 0, 80, 20)  # Mock text boundaries
    mock_draw.text = MagicMock()
    mock_font = MagicMock()
    
    # Default colors configuration
    colors = {
        'background': 255,  # White
        'text': 0,  # Black
        'border_normal': 0,  # Black
        'border_low_stock': 128,  # Gray
        'low_stock_threshold': 2
    }
    
    # Test with quantity > 2 (should use normal border)
    pi_inventory_system.display_manager.create_lozenge(mock_draw, 0, 0, 100, 50, "Test Item", 3, mock_font, colors)
    mock_draw.rounded_rectangle.assert_called_with(
        [(0, 0), (100, 50)], 
        radius=12,  # min(100, 50) // 4
        fill=255,  # White background
        outline=0,  # Black border (normal)
        width=2
    )
    
    # Reset mock for next test
    mock_draw.reset_mock()
    
    # Test with quantity = 2 (should use low stock border)
    pi_inventory_system.display_manager.create_lozenge(mock_draw, 0, 0, 100, 50, "Test Item", 2, mock_font, colors)
    mock_draw.rounded_rectangle.assert_called_with(
        [(0, 0), (100, 50)],
        radius=12,
        fill=255,
        outline=128,  # Gray border (low stock)
        width=2
    )
    
    # Reset mock for next test
    mock_draw.reset_mock()
    
    # Test with quantity < 2 (should use low stock border)
    pi_inventory_system.display_manager.create_lozenge(mock_draw, 0, 0, 100, 50, "Test Item", 1, mock_font, colors)
    mock_draw.rounded_rectangle.assert_called_with(
        [(0, 0), (100, 50)],
        radius=12,
        fill=255,
        outline=128,  # Gray border (low stock)
        width=2
    )
