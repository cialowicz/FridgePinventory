# Tests for display manager module

import pytest
from unittest.mock import patch, MagicMock
import pi_inventory_system.display_manager

@pytest.fixture
def mock_config_manager():
    """Mock the config manager."""
    config_manager = MagicMock()
    config_manager.get_platform_config.return_value = {}
    config_manager.get_layout_config.return_value = {}
    config_manager.get_display_config.return_value = {'colors': {}}
    config_manager.get_font_config.return_value = {'path': 'dummy_font.ttf'}
    return config_manager

def test_is_display_supported(mock_config_manager):
    """Test display support detection."""
    with patch('pi_inventory_system.display_manager._is_raspberry_pi') as mock_is_pi:
        mock_is_pi.return_value = True
        assert pi_inventory_system.display_manager.is_display_supported(mock_config_manager)
    
    with patch('pi_inventory_system.display_manager._is_raspberry_pi') as mock_is_pi:
        mock_is_pi.return_value = False
        assert not pi_inventory_system.display_manager.is_display_supported(mock_config_manager)

def test_initialize_display(mock_config_manager): 
    """Test display initialization."""
    with patch('pi_inventory_system.display_manager.is_display_supported', return_value=True), \
         patch('pi_inventory_system.display_manager.WaveshareDisplay') as mock_waveshare_class:
        mock_display_instance = MagicMock(name="mock_waveshare_display")
        mock_display_instance.initialize.return_value = True
        mock_display_instance.WIDTH = 800
        mock_display_instance.HEIGHT = 480
        mock_waveshare_class.return_value = mock_display_instance

        display = pi_inventory_system.display_manager.initialize_display(mock_config_manager)

        assert display is mock_display_instance
        mock_waveshare_class.assert_called_once()
        mock_display_instance.initialize.assert_called_once()

def test_display_inventory(mock_config_manager):
    """Test inventory display."""
    mock_display = MagicMock()
    mock_display.WIDTH = 800
    mock_display.HEIGHT = 480
    mock_display.display_image = MagicMock()
    mock_db_manager = MagicMock()
    mock_db_manager.get_inventory.return_value = [('Test Item 1', 5), ('Test Item 2', 3)]

    with patch('pi_inventory_system.display_manager.Image'), \
         patch('pi_inventory_system.display_manager.ImageDraw') as mock_draw, \
         patch('pi_inventory_system.display_manager.ImageFont'):
        mock_draw_instance = MagicMock()
        mock_draw_instance.textbbox.return_value = (0, 0, 100, 20)
        mock_draw.Draw.return_value = mock_draw_instance

        result = pi_inventory_system.display_manager.display_inventory(mock_display, mock_db_manager, mock_config_manager)
        
        mock_display.display_image.assert_called_once()
        assert result is True

def test_display_inventory_no_display(mock_config_manager):
    """Test inventory display when no display is available."""
    result = pi_inventory_system.display_manager.display_inventory(None, [], mock_config_manager)
    assert result is False

def test_initialize_display_no_raspberry_pi(mock_config_manager):
    """Test display initialization on non-Raspberry Pi."""
    with patch('pi_inventory_system.display_manager.is_display_supported', return_value=False):
        display = pi_inventory_system.display_manager.initialize_display(mock_config_manager)
        assert display is None

def test_display_text(mock_config_manager):
    """Test text display on Waveshare display."""
    mock_display = MagicMock()
    mock_display.WIDTH = 800
    mock_display.HEIGHT = 480
    mock_display.display_image = MagicMock()
    
    with patch('pi_inventory_system.display_manager.Image'), \
         patch('pi_inventory_system.display_manager.ImageDraw') as mock_draw, \
         patch('pi_inventory_system.display_manager.ImageFont'):
        mock_draw_instance = MagicMock()
        mock_draw_instance.textbbox.return_value = (0, 0, 200, 30)
        mock_draw.Draw.return_value = mock_draw_instance

        result = pi_inventory_system.display_manager.display_text(mock_display, "Test Message", mock_config_manager, font_size=24)
        
        mock_display.display_image.assert_called_once()
        assert result is True

def test_display_text_no_display(mock_config_manager):
    """Test text display when no display is available."""
    result = pi_inventory_system.display_manager.display_text(None, "Test Message", mock_config_manager)
    assert result is False

def test_lozenge_border_color():
    """Test lozenge border color changes based on quantity."""
    mock_draw = MagicMock()
    mock_draw.rounded_rectangle = MagicMock()
    mock_draw.textbbox.return_value = (0, 0, 80, 20)
    mock_draw.text = MagicMock()
    mock_font = MagicMock()
    
    colors = {
        'background': 255,
        'text': 0,
        'border_normal': 0,
        'border_low_stock': 128,
        'low_stock_threshold': 2
    }
    
    pi_inventory_system.display_manager.create_lozenge(mock_draw, 0, 0, 100, 50, "Test Item", 3, mock_font, colors)
    mock_draw.rounded_rectangle.assert_called_with(
        [(0, 0), (100, 50)], 
        radius=12,
        fill=255,
        outline=0,
        width=2
    )
    
    mock_draw.reset_mock()
    
    pi_inventory_system.display_manager.create_lozenge(mock_draw, 0, 0, 100, 50, "Test Item", 2, mock_font, colors)
    mock_draw.rounded_rectangle.assert_called_with(
        [(0, 0), (100, 50)],
        radius=12,
        fill=255,
        outline=128,
        width=2
    )
    
    mock_draw.reset_mock()
    
    pi_inventory_system.display_manager.create_lozenge(mock_draw, 0, 0, 100, 50, "Test Item", 1, mock_font, colors)
    mock_draw.rounded_rectangle.assert_called_with(
        [(0, 0), (100, 50)],
        radius=12,
        fill=255,
        outline=128,
        width=2
    )
