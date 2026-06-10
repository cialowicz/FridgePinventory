# Module for managing the e-Paper display
# Updated for Waveshare 3.97" 800x480 e-Paper HAT+

import os
import logging
import traceback
import time

# Configure logging for this module
logger = logging.getLogger(__name__)

from math import ceil

from PIL import Image, ImageColor, ImageDraw, ImageFont

# Import the Waveshare display driver
from .waveshare_display import WaveshareDisplay

def _is_raspberry_pi(config_manager):
    """Check if we're running on a Raspberry Pi (config-driven for tests)."""
    from .platform_info import is_raspberry_pi
    platform_config = config_manager.get_platform_config() or {}
    return is_raspberry_pi(
        model_file=platform_config.get('raspberry_pi_model_file', '/proc/device-tree/model'),
        required_string=platform_config.get('required_pi_string', 'raspberry pi'),
    )

def _display_hardware_config(config_manager):
    """Return the hardware.display config as a dict, tolerating test doubles."""
    try:
        hardware = config_manager.get_hardware_config() if config_manager is not None else {}
    except Exception:
        hardware = {}
    if not isinstance(hardware, dict):
        return {}
    display_config = hardware.get('display', {})
    return display_config if isinstance(display_config, dict) else {}

def is_display_supported(config_manager) -> bool:
    """Checks if the display is supported on the current platform."""
    display_config = _display_hardware_config(config_manager)
    if not display_config.get('enabled', True):
        logger.info("Display disabled in configuration")
        return False
    supported = _is_raspberry_pi(config_manager)
    logger.info(f"Display supported: {supported}")
    return supported

def initialize_display(config_manager):
    """Initialize the Waveshare e-Paper display if supported.

    Returns the WaveshareDisplay only if real hardware is present; returns
    None when the driver fell back to a mock so the caller does not believe
    output is actually visible.
    """
    logger.info("Attempting to initialize Waveshare display...")
    if not is_display_supported(config_manager):
        logger.warning("Display not supported on this platform")
        return None

    try:
        display = WaveshareDisplay(config_manager=config_manager)
        if not display.initialize():
            logger.warning("Display initialization returned mock; treating as unavailable")
            return None
        logger.info("Waveshare display initialized successfully")
        return display
    except Exception as e:
        logger.error(f"Failed to initialize display: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def _text_width(draw, text, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _fit_text(draw, text, font, max_width) -> str:
    """Ellipsize text to fit inside max_width."""
    if _text_width(draw, text, font) <= max_width:
        return text
    suffix = "..."
    if _text_width(draw, suffix, font) > max_width:
        return ""
    low, high = 0, len(text)
    best = suffix
    while low <= high:
        mid = (low + high) // 2
        candidate = text[:mid].rstrip() + suffix
        if _text_width(draw, candidate, font) <= max_width:
            best = candidate
            low = mid + 1
        else:
            high = mid - 1
    return best


def _positive_int(value, default: int, *, allow_zero: bool = False) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < 0 or (parsed == 0 and not allow_zero):
        return default
    return parsed


# The panel supports exactly four gray levels; map the common color names to
# the level the driver's 4-gray quantizer will actually produce.
_NAMED_GRAYS = {
    'white': 0xFF,
    'light gray': 0xC0, 'light grey': 0xC0,
    'light_gray': 0xC0, 'light_grey': 0xC0,
    'lightgray': 0xC0, 'lightgrey': 0xC0,
    'gray': 0x80, 'grey': 0x80,
    'dark gray': 0x80, 'dark grey': 0x80,
    'dark_gray': 0x80, 'dark_grey': 0x80,
    'darkgray': 0x80, 'darkgrey': 0x80,
    'black': 0x00,
}


def _gray_value(value, default: int) -> int:
    """Resolve a configured color (gray level int or color name) to 0-255."""
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return min(255, max(0, int(value)))
    if isinstance(value, str):
        named = _NAMED_GRAYS.get(value.strip().lower())
        if named is not None:
            return named
        try:
            resolved = ImageColor.getcolor(value, 'L')
            if isinstance(resolved, int):
                return resolved
        except ValueError:
            pass
        logger.warning(f"Unrecognized display color {value!r}; using {default}")
        return default
    return default


def create_lozenge(draw, x, y, width, height, item_name, quantity, font, colors):
    """Create a lozenge shape with item name and quantity.
    
    Args:
        draw: PIL ImageDraw instance
        x, y: Top-left coordinates
        width, height: Size of lozenge
        item_name: Name of the item
        quantity: Quantity of the item
        font: Font to use
        colors: Color configuration dict
    """
    # Get colors (resolved to grayscale levels for the Waveshare panel)
    background_color = _gray_value(colors.get('background'), 255)  # White
    text_color = _gray_value(colors.get('text'), 0)  # Black
    border_normal = _gray_value(colors.get('border_normal'), 0)  # Black
    border_low_stock = _gray_value(colors.get('border_low_stock'), 128)  # Gray
    low_stock_threshold = colors.get('low_stock_threshold', 2)
    
    # Determine border color based on quantity
    quantity_is_number = isinstance(quantity, (int, float))
    border_color = (
        border_low_stock
        if quantity_is_number and quantity <= low_stock_threshold
        else border_normal
    )
    
    # Draw rounded rectangle (lozenge)
    radius = min(width, height) // 4
    draw.rounded_rectangle(
        [(x, y), (x + width, y + height)],
        radius=radius,
        fill=background_color,
        outline=border_color,
        width=2
    )
    
    # Add item name and quantity
    text = item_name if quantity is None else f"{item_name}: {quantity}"
    text = _fit_text(draw, text, font, max(0, width - 12))
    
    # Get text size
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    # Center text in lozenge
    text_x = x + (width - text_width) // 2
    text_y = y + (height - text_height) // 2
    
    draw.text((text_x, text_y), text, fill=text_color, font=font)

def _render(display, draw_fn, label: str) -> bool:
    """Shared boilerplate: validate display, build a white L-mode image, run
    draw_fn(draw, image), push to the panel."""
    if not display:
        logger.warning(f"No display available for {label}")
        return False
    if not hasattr(display, 'WIDTH') or not hasattr(display, 'HEIGHT'):
        logger.error("Display object missing WIDTH or HEIGHT attributes")
        return False
    try:
        image = Image.new("L", (display.WIDTH, display.HEIGHT), 255)
        draw = ImageDraw.Draw(image)
        draw_fn(draw, image)
        display.display_image(image)
        return True
    except Exception as e:
        logger.error(f"Unexpected error during {label}: {e}")
        logger.error(traceback.format_exc())
        return False


def display_inventory(display, inventory, config_manager):
    """Display the current inventory on the Waveshare display."""

    def _draw(draw, image):

        
        if not inventory:
            font = _load_font(config_manager, size=32)
            text = "No items in inventory"
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_x = (display.WIDTH - (text_bbox[2] - text_bbox[0])) // 2
            text_y = (display.HEIGHT - (text_bbox[3] - text_bbox[1])) // 2
            draw.text((text_x, text_y), text, fill=0, font=font)
            return

        layout_config = config_manager.get_layout_config()
        items_per_row = _positive_int(layout_config.get('items_per_row'), 4)
        margin = _positive_int(layout_config.get('margin'), 20, allow_zero=True)
        spacing = _positive_int(layout_config.get('spacing'), 15, allow_zero=True)
        lozenge_height = _positive_int(layout_config.get('lozenge_height'), 60)

        available_width = display.WIDTH - (2 * margin) - ((items_per_row - 1) * spacing)
        lozenge_width = available_width // items_per_row
        available_height = display.HEIGHT - (2 * margin)
        rows_per_page = available_height // (lozenge_height + spacing)
        max_items = rows_per_page * items_per_row

        # layout.font_size overrides; otherwise display.font.size from config.
        font = _load_font(config_manager, size=layout_config.get('font_size'))
        header_font = _load_font(config_manager, size=24)
        timestamp_font = _load_font(config_manager, size=14)
        color_config = config_manager.get('display', 'colors', default={})

        header_text = "Fridge Inventory"
        header_bbox = draw.textbbox((0, 0), header_text, font=header_font)
        header_x = (display.WIDTH - (header_bbox[2] - header_bbox[0])) // 2
        draw.text((header_x, 10), header_text, fill=0, font=header_font)

        start_y = 50
        items_displayed = 0
        inventory_to_render = list(inventory)
        if len(inventory_to_render) > max_items and max_items > 0:
            hidden_count = len(inventory_to_render) - max_items + 1
            inventory_to_render = inventory_to_render[:max_items - 1]
            inventory_to_render.append((f"+{hidden_count} more", None))

        for i, item in enumerate(inventory_to_render[:max_items]):
            if not isinstance(item, (tuple, list)) or len(item) < 2:
                logger.warning(f"Invalid inventory item format at index {i}: {item}")
                continue
            item_name, quantity = item
            if not isinstance(item_name, str):
                item_name = str(item_name)
            if quantity is not None and not isinstance(quantity, (int, float)):
                try:
                    quantity = int(quantity)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid quantity for {item_name}: {quantity}")
                    quantity = 0

            row = items_displayed // items_per_row
            col = items_displayed % items_per_row
            x = margin + col * (lozenge_width + spacing)
            y = start_y + row * (lozenge_height + spacing)
            if y + lozenge_height > display.HEIGHT - margin:
                logger.info(f"Reached display limit at item {i}")
                break

            create_lozenge(draw, x, y, lozenge_width, lozenge_height,
                           item_name, quantity, font, color_config)
            items_displayed += 1

        timestamp = time.strftime("Updated %Y-%m-%d %H:%M")
        ts_bbox = draw.textbbox((0, 0), timestamp, font=timestamp_font)
        draw.text((display.WIDTH - (ts_bbox[2] - ts_bbox[0]) - 10,
                   display.HEIGHT - 25),
                  timestamp, fill=128, font=timestamp_font)
        logger.info(f"Displayed {items_displayed} inventory items")

    return _render(display, _draw, "inventory display")

_FONT_CACHE: dict = {}


def _load_font(config_manager, size=None):
    """Load (and cache) a font with fallback options.

    When size is None, display.font.size from config is used (default 24).
    """
    font_config = config_manager.get_font_config()
    primary_path = font_config.get('path', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    if size is None:
        size = font_config.get('size')
    size = _positive_int(size, 24)
    cache_key = (primary_path, size)
    cached = _FONT_CACHE.get(cache_key)
    if cached is not None:
        return cached

    font_paths_to_try = [
        primary_path,
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
    ]
    for path in font_paths_to_try:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _FONT_CACHE[cache_key] = font
                return font
            except Exception as e:
                logger.debug(f"Failed to load font from {path}: {e}")
                continue

    logger.warning("Failed to load any TrueType font, using default")
    fallback = ImageFont.load_default()
    _FONT_CACHE[cache_key] = fallback
    return fallback

def cleanup_display(display, config_manager=None):
    """Clean up display resources.
    
    Args:
        display: Display instance to clean up.
    """
    if not display:
        return
    
    try:
        clear_on_shutdown = False
        if config_manager is not None:
            clear_on_shutdown = bool(
                config_manager.get('display', 'clear_on_shutdown', default=False)
            )

        if clear_on_shutdown and hasattr(display, 'clear'):
            display.clear()
            logger.info("Display cleared")
        
        # Call cleanup method
        if hasattr(display, 'cleanup'):
            display.cleanup()
            logger.info("Display resources cleaned up")
        
        logger.info("Display cleanup completed")
    except Exception as e:
        logger.error(f"Error during display cleanup: {e}")

def display_text(display, text, config_manager, font_size=24):
    """Display text on the Waveshare display with word wrap that preserves \\n."""
    if not text:
        text = " "
    elif not isinstance(text, str):
        text = str(text)

    def _draw(draw, image):
        font = _load_font(config_manager, size=font_size)
        max_width = display.WIDTH - 40

        text_lines = []
        for paragraph in text.split("\n"):
            words = paragraph.split()
            if not words:
                text_lines.append("")
                continue
            current_line = ""
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] - bbox[0] <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        text_lines.append(current_line)
                        if _text_width(draw, word, font) <= max_width:
                            current_line = word
                        else:
                            text_lines.append(_fit_text(draw, word, font, max_width))
                            current_line = ""
                    else:
                        text_lines.append(_fit_text(draw, word, font, max_width))
                        current_line = ""
            if current_line:
                text_lines.append(current_line)

        line_height = getattr(font, "size", font_size) + 8
        total_height = len(text_lines) * line_height
        start_y = (display.HEIGHT - total_height) // 2

        for i, line in enumerate(text_lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (display.WIDTH - (bbox[2] - bbox[0])) // 2
            draw.text((x, start_y + i * line_height), line, fill=0, font=font)
        logger.info(f"Displayed text: {text[:50] + '...' if len(text) > 50 else text}")

    return _render(display, _draw, "text display")
