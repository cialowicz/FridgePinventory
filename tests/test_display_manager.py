# Tests for display manager module

import pytest
from unittest.mock import patch, MagicMock
from PIL import Image, ImageFont
import pi_inventory_system.display_manager
import pi_inventory_system.waveshare_display as waveshare_display
from pi_inventory_system.waveshare_display import WaveshareDisplay

@pytest.fixture
def mock_config_manager():
    """Mock the config manager."""
    config_manager = MagicMock()
    config_manager.get_platform_config.return_value = {}
    config_manager.get_hardware_config.return_value = {'display': {'enabled': True}}
    config_manager.get_layout_config.return_value = {}
    config_manager.get_display_config.return_value = {'colors': {}}
    config_manager.get_font_config.return_value = {'path': 'dummy_font.ttf'}
    config_manager.get.return_value = {}
    return config_manager

def test_is_display_supported(mock_config_manager):
    """Test display support detection."""
    with patch('pi_inventory_system.display_manager._is_raspberry_pi') as mock_is_pi:
        mock_is_pi.return_value = True
        assert pi_inventory_system.display_manager.is_display_supported(mock_config_manager)
    
    with patch('pi_inventory_system.display_manager._is_raspberry_pi') as mock_is_pi:
        mock_is_pi.return_value = False
        assert not pi_inventory_system.display_manager.is_display_supported(mock_config_manager)


def test_is_display_supported_honors_disabled_config():
    config_manager = MagicMock()
    config_manager.get_hardware_config.return_value = {'display': {'enabled': False}}
    assert not pi_inventory_system.display_manager.is_display_supported(config_manager)

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
    inventory = [('Test Item 1', 5), ('Test Item 2', 3)]

    with patch('pi_inventory_system.display_manager.Image'), \
         patch('pi_inventory_system.display_manager.ImageDraw') as mock_draw, \
         patch('pi_inventory_system.display_manager.ImageFont'):
        mock_draw_instance = MagicMock()
        mock_draw_instance.textbbox.return_value = (0, 0, 100, 20)
        mock_draw.Draw.return_value = mock_draw_instance

        result = pi_inventory_system.display_manager.display_inventory(
            mock_display,
            inventory,
            mock_config_manager,
        )

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

        result = pi_inventory_system.display_manager.display_text(
            mock_display,
            "Test Message",
            mock_config_manager,
            font_size=24,
        )
        
        mock_display.display_image.assert_called_once()
        assert result is True

def test_display_text_no_display(mock_config_manager):
    """Test text display when no display is available."""
    result = pi_inventory_system.display_manager.display_text(
        None,
        "Test Message",
        mock_config_manager,
    )
    assert result is False


def test_cleanup_display_does_not_clear_by_default(mock_config_manager):
    display = MagicMock()
    mock_config_manager.get.return_value = False

    pi_inventory_system.display_manager.cleanup_display(display, mock_config_manager)

    display.clear.assert_not_called()
    display.cleanup.assert_called_once()


def test_waveshare_display_image_propagates_hardware_failure():
    display = WaveshareDisplay.__new__(WaveshareDisplay)
    display._initialized = True
    display._display = MagicMock()
    display._display.getbuffer_4Gray.return_value = []
    display._display.display_4GRAY.side_effect = RuntimeError("panel busy")

    image = Image.new("L", (display.WIDTH, display.HEIGHT), 255)

    with pytest.raises(RuntimeError, match="panel busy"):
        display.display_image(image)


def test_waveshare_display_image_falls_back_without_4gray_methods():
    class BasicDisplay:
        def __init__(self):
            self.displayed_buffer = None

        def getbuffer(self, image):
            assert image.mode == "1"
            return ["basic-buffer"]

        def display(self, buffer):
            self.displayed_buffer = buffer

    display = WaveshareDisplay.__new__(WaveshareDisplay)
    display._initialized = True
    display._display = BasicDisplay()

    image = Image.new("L", (display.WIDTH, display.HEIGHT), 255)

    display.display_image(image)

    assert display._display.displayed_buffer == ["basic-buffer"]


def test_waveshare_driver_matching_accepts_exact_resolution():
    class Module:
        class EPD:
            width = 800
            height = 480

    assert waveshare_display._driver_matches_display(Module, "test-driver") is True


def test_waveshare_init_skips_test_pattern_by_default():
    display = WaveshareDisplay.__new__(WaveshareDisplay)
    display._initialized = False
    display._display = None
    display._is_mock = False
    display._show_test_pattern = False
    display._epd_instance = MagicMock()
    display._epd_instance.init_4GRAY.return_value = 0

    assert display.init_display() is True

    display._epd_instance.Clear.assert_called_once()
    display._epd_instance.display_4GRAY.assert_not_called()
    assert display._display is display._epd_instance


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
    
    pi_inventory_system.display_manager.create_lozenge(
        mock_draw,
        0,
        0,
        100,
        50,
        "Test Item",
        3,
        mock_font,
        colors,
    )
    mock_draw.rounded_rectangle.assert_called_with(
        [(0, 0), (100, 50)], 
        radius=12,
        fill=255,
        outline=0,
        width=2
    )
    
    mock_draw.reset_mock()
    
    pi_inventory_system.display_manager.create_lozenge(
        mock_draw,
        0,
        0,
        100,
        50,
        "Test Item",
        2,
        mock_font,
        colors,
    )
    mock_draw.rounded_rectangle.assert_called_with(
        [(0, 0), (100, 50)],
        radius=12,
        fill=255,
        outline=128,
        width=2
    )
    
    mock_draw.reset_mock()
    
    pi_inventory_system.display_manager.create_lozenge(
        mock_draw,
        0,
        0,
        100,
        50,
        "Test Item",
        1,
        mock_font,
        colors,
    )
    mock_draw.rounded_rectangle.assert_called_with(
        [(0, 0), (100, 50)],
        radius=12,
        fill=255,
        outline=128,
        width=2
    )


def test_gray_value_resolves_names_and_numbers():
    gray = pi_inventory_system.display_manager._gray_value
    assert gray('white', 0) == 255
    assert gray('black', 255) == 0
    assert gray('gray', 0) == 128
    assert gray('grey', 0) == 128
    assert gray(128, 0) == 128
    assert gray(300, 0) == 255  # clamped
    assert gray(-5, 255) == 0  # clamped
    assert gray(None, 77) == 77
    assert gray('not-a-color', 77) == 77
    # CSS names resolve via their grayscale luminance
    assert gray('yellow', 0) == 226


def test_lozenge_accepts_named_colors():
    """Shipped config uses color names; they must resolve to gray levels."""
    mock_draw = MagicMock()
    mock_draw.textbbox.return_value = (0, 0, 80, 20)
    mock_font = MagicMock()

    colors = {
        'background': 'white',
        'text': 'black',
        'border_normal': 'black',
        'border_low_stock': 'gray',
        'low_stock_threshold': 2,
    }

    pi_inventory_system.display_manager.create_lozenge(
        mock_draw, 0, 0, 100, 50, "Test Item", 1, mock_font, colors,
    )
    mock_draw.rounded_rectangle.assert_called_with(
        [(0, 0), (100, 50)],
        radius=12,
        fill=255,
        outline=128,
        width=2,
    )
    assert mock_draw.text.call_args.kwargs['fill'] == 0


def test_default_config_low_stock_border_is_visible():
    """The shipped low-stock border color must render visibly darker than the
    white background on the grayscale panel (regression: 'yellow' -> 226)."""
    from pi_inventory_system.config_manager import DEFAULT_CONFIG

    colors = DEFAULT_CONFIG['display']['colors']
    border = pi_inventory_system.display_manager._gray_value(
        colors['border_low_stock'], 128
    )
    background = pi_inventory_system.display_manager._gray_value(
        colors['background'], 255
    )
    assert border <= 128
    assert background - border >= 64


def test_load_font_uses_configured_size(mock_config_manager, tmp_path):
    """display.font.size from config must be honored when no size is passed."""
    font_file = tmp_path / "font.ttf"
    font_file.write_bytes(b"stub")
    mock_config_manager.get_font_config.return_value = {
        'path': str(font_file),
        'size': 16,
    }

    pi_inventory_system.display_manager._FONT_CACHE.clear()
    with patch('pi_inventory_system.display_manager.ImageFont') as mock_font:
        mock_font.truetype.return_value = MagicMock()
        pi_inventory_system.display_manager._load_font(mock_config_manager)

    mock_font.truetype.assert_called_once_with(str(font_file), 16)


def test_display_inventory_item_font_uses_configured_size(mock_config_manager, tmp_path):
    """Item lozenges must render with display.font.size, not a hardcoded 24."""
    font_file = tmp_path / "font.ttf"
    font_file.write_bytes(b"stub")
    mock_config_manager.get_font_config.return_value = {
        'path': str(font_file),
        'size': 16,
    }
    mock_display = MagicMock()
    mock_display.WIDTH = 800
    mock_display.HEIGHT = 480

    pi_inventory_system.display_manager._FONT_CACHE.clear()
    with patch('pi_inventory_system.display_manager.ImageFont') as mock_font:
        mock_font.truetype.return_value = ImageFont.load_default()
        assert pi_inventory_system.display_manager.display_inventory(
            mock_display,
            [("salmon", 1)],
            mock_config_manager,
        )

    sizes = [call.args[1] for call in mock_font.truetype.call_args_list]
    assert 16 in sizes
    assert 24 in sizes  # header stays at its explicit size


def test_lozenge_ellipsizes_long_text():
    mock_draw = MagicMock()
    mock_draw.textbbox.side_effect = lambda _pos, text, font=None: (0, 0, len(text) * 10, 20)
    mock_font = MagicMock()
    colors = {'background': 255, 'text': 0, 'border_normal': 0}

    pi_inventory_system.display_manager.create_lozenge(
        mock_draw,
        0,
        0,
        100,
        50,
        "very long freezer inventory item name",
        3,
        mock_font,
        colors,
    )

    rendered_text = mock_draw.text.call_args.args[1]
    assert rendered_text.endswith("...")
    assert len(rendered_text) * 10 <= 88


def test_display_inventory_reports_overflow(mock_config_manager):
    mock_display = MagicMock()
    mock_display.WIDTH = 800
    mock_display.HEIGHT = 480
    mock_display.display_image = MagicMock()
    inventory = [(f"Item {i}", i + 1) for i in range(21)]

    with patch('pi_inventory_system.display_manager.create_lozenge') as lozenge, \
         patch('pi_inventory_system.display_manager._load_font',
               return_value=ImageFont.load_default()):
        assert pi_inventory_system.display_manager.display_inventory(
            mock_display,
            inventory,
            mock_config_manager,
        )

    rendered_names = [call.args[5] for call in lozenge.call_args_list]
    assert rendered_names[-1] == "+2 more"


def test_display_inventory_sanitizes_invalid_layout(mock_config_manager):
    mock_config_manager.get_layout_config.return_value = {
        'items_per_row': 0,
        'spacing': -1,
        'margin': -1,
        'lozenge_height': 0,
    }
    mock_display = MagicMock()
    mock_display.WIDTH = 800
    mock_display.HEIGHT = 480
    mock_display.display_image = MagicMock()

    with patch('pi_inventory_system.display_manager._load_font',
               return_value=ImageFont.load_default()):
        assert pi_inventory_system.display_manager.display_inventory(
            mock_display,
            [("salmon", 1)],
            mock_config_manager,
        )


def test_waveshare_driver_matching_rejects_unknown_dimensions():
    """A driver that cannot report its panel size cannot be validated against
    the 800x480 buffers this app builds; it must be rejected, not assumed."""
    class Module:
        class EPD:
            pass

    assert waveshare_display._driver_matches_display(Module, "test-driver") is False
