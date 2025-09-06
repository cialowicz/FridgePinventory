# Module for managing the e-Paper display
# Updated for Waveshare 3.97" 800x480 e-Paper HAT+

import os
import logging
import traceback
import time

# Configure logging for this module
logger = logging.getLogger(__name__)

from math import ceil

from PIL import Image, ImageDraw, ImageFont

# Import the Waveshare display driver
from .waveshare_display import WaveshareDisplay

def _is_raspberry_pi(config_manager):
    """Check if we're running on a Raspberry Pi."""
    # Get platform configuration
    platform_config = config_manager.get_platform_config()
    model_file = platform_config.get('raspberry_pi_model_file', '/proc/device-tree/model')
    required_string = platform_config.get('required_pi_string', 'raspberry pi')
    
    # Check for Raspberry Pi specific files
    if os.path.exists(model_file):
        try:
            with open(model_file, 'r') as f:
                model = f.read().lower()
                return required_string in model
        except (IOError, OSError) as e:
            logger.warning(f"Could not read platform model file {model_file}: {e}")
            return False
    return False

def is_display_supported(config_manager) -> bool:
    """Checks if the display is supported on the current platform."""
    supported = _is_raspberry_pi(config_manager)
    logger.info(f"Display supported: {supported}")
    return supported

def initialize_display(config_manager):
    """Initializes the Waveshare e-Paper display if supported."""
    logger.info("Attempting to initialize Waveshare display...")
    if not is_display_supported(config_manager):
        logger.warning("Display not supported on this platform")
        return None
    
    try:
        display = WaveshareDisplay()
        if display.initialize():
            logger.info("Waveshare display initialized successfully")
            return display
        else:
            logger.warning("Failed to initialize Waveshare display")
            return None
    except Exception as e:
        logger.error(f"Failed to initialize display: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

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
    # Get colors (using grayscale values for Waveshare)
    background_color = colors.get('background', 255)  # White
    text_color = colors.get('text', 0)  # Black
    border_normal = colors.get('border_normal', 0)  # Black
    border_low_stock = colors.get('border_low_stock', 128)  # Gray
    low_stock_threshold = colors.get('low_stock_threshold', 2)
    
    # Determine border color based on quantity
    border_color = border_low_stock if quantity <= low_stock_threshold else border_normal
    
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
    text = f"{item_name}: {quantity}"
    
    # Get text size
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    # Center text in lozenge
    text_x = x + (width - text_width) // 2
    text_y = y + (height - text_height) // 2
    
    draw.text((text_x, text_y), text, fill=text_color, font=font)

def display_inventory(display, inventory, config_manager):
    """Display the current inventory on the Waveshare display.

    Args:
        display: The display object.
        inventory: A list of tuples (item_name, quantity) to display.
        config_manager: Configuration manager instance
    """
    if not display:
        logger.warning("No display available for inventory display")
        return False

    try:
        # Validate display object
        if not hasattr(display, 'WIDTH') or not hasattr(display, 'HEIGHT'):
            logger.error("Display object missing WIDTH or HEIGHT attributes")
            return False
        
        # Create a new image with 800x480 resolution
        image = Image.new("L", (display.WIDTH, display.HEIGHT), 255)  # White background
        draw = ImageDraw.Draw(image)
        

        
        if not inventory:
            logger.info("No inventory to display, showing empty message")
            # Draw "No items" message
            font = _load_font(config_manager, size=32)
            text = "No items in inventory"
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = (display.WIDTH - text_width) // 2
            text_y = (display.HEIGHT - text_height) // 2
            draw.text((text_x, text_y), text, fill=0, font=font)
            display.display_image(image)
            return True
        
        # Load font from configuration
        font_size = config_manager.get_layout_config().get('font_size', 24)
        font = _load_font(config_manager, size=font_size)
        
        # Get color configuration
        color_config = config_manager.get('display', 'colors', default={})
        
        # Calculate layout for 800x480 display
        layout_config = config_manager.get_layout_config()
        
        # Optimized layout for 800x480
        # Can fit more items with better resolution
        items_per_row = layout_config.get('items_per_row', 4)  # More items per row
        margin = layout_config.get('margin', 20)
        spacing = layout_config.get('spacing', 15)
        lozenge_height = layout_config.get('lozenge_height', 60)
        
        # Calculate lozenge width based on available space
        available_width = display.WIDTH - (2 * margin) - ((items_per_row - 1) * spacing)
        lozenge_width = available_width // items_per_row
        
        # Calculate how many rows we can fit
        available_height = display.HEIGHT - (2 * margin)
        rows_per_page = available_height // (lozenge_height + spacing)
        max_items = rows_per_page * items_per_row
        
        # Draw header
        header_font = _load_font(config_manager, size=24)
        header_text = "Fridge Inventory"
        header_bbox = draw.textbbox((0, 0), header_text, font=header_font)
        header_width = header_bbox[2] - header_bbox[0]
        header_x = (display.WIDTH - header_width) // 2
        draw.text((header_x, 10), header_text, fill=0, font=header_font)
        
        # Adjust starting Y position to account for header
        start_y = 50
        
        # Draw inventory items
        items_displayed = 0
        for i, item in enumerate(inventory[:max_items]):
            try:
                # Validate item format
                if not isinstance(item, (tuple, list)) or len(item) < 2:
                    logger.warning(f"Invalid inventory item format at index {i}: {item}")
                    continue
                
                item_name, quantity = item
                
                # Validate and convert data
                if not isinstance(item_name, str):
                    item_name = str(item_name)
                if not isinstance(quantity, (int, float)):
                    try:
                        quantity = int(quantity)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid quantity for {item_name}: {quantity}")
                        quantity = 0
                
                row = items_displayed // items_per_row
                col = items_displayed % items_per_row
                
                x = margin + col * (lozenge_width + spacing)
                y = start_y + row * (lozenge_height + spacing)
                
                # Check if item fits on display
                if y + lozenge_height > display.HEIGHT - margin:
                    logger.info(f"Reached display limit at item {i}")
                    break
                
                create_lozenge(draw, x, y, lozenge_width, lozenge_height,
                              item_name, quantity, font, color_config)
                items_displayed += 1
                
            except Exception as e:
                logger.error(f"Error drawing item {i}: {e}")
                continue
        
        # Add timestamp at bottom
        timestamp = time.strftime("%Y-%m-%d %H:%M")
        timestamp_font = _load_font(config_manager, size=14)
        timestamp_bbox = draw.textbbox((0, 0), timestamp, font=timestamp_font)
        timestamp_width = timestamp_bbox[2] - timestamp_bbox[0]
        timestamp_x = display.WIDTH - timestamp_width - 10
        timestamp_y = display.HEIGHT - 25
        draw.text((timestamp_x, timestamp_y), timestamp, fill=128, font=timestamp_font)  # Gray
        
        # Update display
        logger.info(f"Displaying {items_displayed} items on Waveshare display")
        display.display_image(image)
        return True
    
    except Exception as e:
        logger.error(f"Unexpected error displaying inventory: {e}")
        logger.error(traceback.format_exc())
        return False

def _load_font(config_manager, size=18):
    """Load a font with fallback options.
    
    Args:
        size: Font size to load
        
    Returns:
        PIL ImageFont instance
    """
    font_config = config_manager.get_font_config()
    font_path = font_config.get('path', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    
    font_paths_to_try = [
        font_path,
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/System/Library/Fonts/Helvetica.ttc'  # macOS fallback
    ]
    
    for path in font_paths_to_try:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception as e:
                logger.debug(f"Failed to load font from {path}: {e}")
                continue
    
    logger.warning("Failed to load any TrueType font, using default")
    return ImageFont.load_default()

def cleanup_display(display):
    """Clean up display resources.
    
    Args:
        display: Display instance to clean up.
    """
    if not display:
        return
    
    try:
        # Clear the display before cleanup
        if hasattr(display, 'clear'):
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
    """Display text on the Waveshare display with improved error handling.
    
    Args:
        display: Display instance
        text: Text to display
        font_size: Size of the font
    """
    if not display:
        logger.warning("No display available for text display")
        return False
    
    try:
        # Validate display object
        if not hasattr(display, 'WIDTH') or not hasattr(display, 'HEIGHT'):
            logger.error("Display object missing WIDTH or HEIGHT attributes")
            return False
        
        # Validate text input
        if not text:
            text = " "  # Display blank if no text
        elif not isinstance(text, str):
            text = str(text)
        
        # Create a new image
        image = Image.new("L", (display.WIDTH, display.HEIGHT), 255)  # White background
        draw = ImageDraw.Draw(image)
        
        # Load font
        font = _load_font(config_manager, size=font_size)
        
        # Handle text that might be too long with word wrapping
        max_width = display.WIDTH - 40  # Leave margins
        text_lines = []
        
        # Simple text wrapping
        words = text.split()
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    text_lines.append(current_line)
                current_line = word
        
        if current_line:
            text_lines.append(current_line)
        
        # Calculate position for centered multi-line text
        line_height = font.size + 8
        total_height = len(text_lines) * line_height
        start_y = (display.HEIGHT - total_height) // 2
        
        # Draw each line
        for i, line in enumerate(text_lines):
            text_bbox = draw.textbbox((0, 0), line, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_x = (display.WIDTH - text_width) // 2
            text_y = start_y + i * line_height
            draw.text((text_x, text_y), line, fill=0, font=font)  # Black text
        
        # Update display
        logger.info(f"Displaying text: {text[:50]}..." if len(text) > 50 else f"Displaying text: {text}")
        display.display_image(image)
        return True
    
    except Exception as e:
        logger.error(f"Unexpected error displaying text: {e}")
        logger.error(traceback.format_exc())
        return False
