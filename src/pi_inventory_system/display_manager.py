# Module for managing the eInk display

import os
import logging
import traceback
import time

# Configure logging for this module
logger = logging.getLogger(__name__)

from math import ceil
from pi_inventory_system.config_manager import config

INKY_AVAILABLE = False

def _is_raspberry_pi():
    """Check if we're running on a Raspberry Pi."""
    # Get platform configuration
    platform_config = config.get_platform_config()
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

# Initialize display support
is_raspberry_pi = _is_raspberry_pi()
logger.info(f"Initial Raspberry Pi check: {is_raspberry_pi}")

if is_raspberry_pi:
    try:
        # Renamed import to avoid conflict if 'auto' is used as a variable name elsewhere
        from inky.auto import auto as auto_inky_display 
        # from inky import InkyPHAT, InkyWHAT # For specific display types
        # from inky import Inky # If using a specific model like InkyImpression
        INKY_AVAILABLE = True
        logger.info("Inky library successfully imported.")
    except ImportError as e:
        # Log the import error for Inky specifically
        logger.warning(f"Inky library not found or failed to import: {e}. Display will not be available.")
        INKY_AVAILABLE = False
    except Exception as e:
        logger.error(f"An unexpected error occurred during Inky import: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        INKY_AVAILABLE = False
else:
    logger.info("Not a Raspberry Pi platform. Inky display will not be available.")
    INKY_AVAILABLE = False

from PIL import Image, ImageDraw, ImageFont

if Image is None:
    logger.critical("Critical Error: PIL.Image is None immediately after import!")
else:
    logger.info(f"PIL.Image imported: type is {type(Image)}")

Inky = None

def is_display_supported() -> bool:
    """Checks if the display is supported on the current platform."""
    supported = is_raspberry_pi and INKY_AVAILABLE
    logger.info(f"Checking if display is supported. Is Raspberry Pi: {is_raspberry_pi}, Is Inky Lib Available: {INKY_AVAILABLE}. Result: {supported}")
    return supported

def initialize_display():
    """Initializes the eInk display if supported."""
    logger.info("Attempting to initialize Inky display...")
    if not is_display_supported():
        # The reason (not Pi or Inky lib missing) would have been logged by is_display_supported or module init.
        logger.warning("Display not supported on this platform or Inky library missing. Cannot initialize.")
        return None
    try:
        logger.info("Using Inky auto-detection (inky.auto.auto) with verbose=True.")
        # The auto() function tries to guess the display type.
        # verbose=True can help debug which display it's trying.
        # For InkyImpression, you might need to pass resolution, e.g. auto_inky_display(verbose=True, resolution=(600, 448))
        display = auto_inky_display(verbose=True)
        logger.info(f"Inky display auto-detected and initialized. Display object: {type(display)}")
        
        # ---- Example for specific Inky display (if auto-detection fails) ----
        # If auto-detection fails, or you know your display type, initialize it directly.
        # Common types: InkyPHAT (red, black, yellow), InkyWHAT (red, black, yellow)
        # from inky import InkyPHAT
        # Known colors for InkyPHAT/WHAT: "red", "black", "yellow" (check your model)
        # Example for a red Inky pHAT:
        # logger.info("Attempting to initialize InkyPHAT('red') specifically as an alternative.")
        # display = InkyPHAT('red')
        # logger.info("Successfully initialized InkyPHAT('red').")
        # ---- End example ----

        # Perform a basic operation to confirm it's working.
        logger.info("Setting display border to white and calling show() as a test.")
        display.set_border(display.WHITE) 
        display.show() # This will clear the screen or show the current buffer contents.
        logger.info("Display initialized and test (set_border, show) completed.")
        return display
    except Exception as e:
        logger.error(f"Failed to initialize Inky display during auto-detection or test: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def create_lozenge(draw, x, y, width, height, item_name, quantity, font):
    """Create a lozenge shape with item name and quantity."""
    # Get color configuration
    color_config = config.get('display', 'colors', default={})
    background_color = color_config.get('background', 'white')
    text_color = color_config.get('text', 'black')
    border_normal = color_config.get('border_normal', 'black')
    border_low_stock = color_config.get('border_low_stock', 'yellow')
    low_stock_threshold = color_config.get('low_stock_threshold', 2)
    
    # Determine border color based on quantity
    border_color = border_low_stock if quantity <= low_stock_threshold else border_normal
    
    # Draw the lozenge shape
    draw.rectangle([(x, y), (x + width, y + height)], fill=background_color, outline=border_color)
    
    # Add item name and quantity
    text = f"{item_name}: {quantity}"
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    text_x = x + (width - text_width) // 2
    text_y = y + (height - text_height) // 2
    
    draw.text((text_x, text_y), text, fill=text_color, font=font)

def display_inventory(display, inventory):
    """Display the current inventory on the Inky display.

    Args:
        display: The display object.
        inventory: A list of tuples (item_name, quantity) to display.
    """
    if not display:
        logger.warning("No display available for inventory display")
        return False

    try:
        # Validate display object has required attributes
        if not hasattr(display, 'WIDTH') or not hasattr(display, 'HEIGHT'):
            logger.error("Display object missing WIDTH or HEIGHT attributes")
            return False
        
        if not hasattr(display, 'set_image') or not hasattr(display, 'show'):
            logger.error("Display object missing set_image or show methods")
            return False
        
        if not inventory:
            logger.info("No inventory to display, clearing display")
            # Clear display with empty image
            try:
                image = Image.new("P", (display.WIDTH, display.HEIGHT))
                draw = ImageDraw.Draw(image)
                # Draw "No items" message
                font = ImageFont.load_default()
                text = "No items in inventory"
                text_bbox = draw.textbbox((0, 0), text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                text_x = (display.WIDTH - text_width) // 2
                text_y = (display.HEIGHT - text_height) // 2
                draw.text((text_x, text_y), text, fill='black', font=font)
                display.set_image(image)
                display.show()
            except Exception as e:
                logger.error(f"Error clearing display: {e}")
                return False
            return True
        
        # Validate inventory data
        if not isinstance(inventory, (list, tuple)):
            logger.error(f"Invalid inventory type: {type(inventory)}")
            return False
        
        # Create a new image
        image = Image.new("P", (display.WIDTH, display.HEIGHT))
        draw = ImageDraw.Draw(image)
        
        # Load font from configuration with better error handling
        font_config = config.get_font_config()
        font_path = font_config.get('path', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
        font_size = font_config.get('size', 16)
        fallback_size = font_config.get('fallback_size', 12)
        
        font = None
        font_paths_to_try = [
            font_path,
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/System/Library/Fonts/Helvetica.ttc'  # macOS fallback
        ]
        
        for path in font_paths_to_try:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, font_size)
                    logger.debug(f"Loaded font from {path}")
                    break
                except Exception as e:
                    logger.debug(f"Failed to load font from {path}: {e}")
                    continue
        
        if font is None:
            logger.warning("Failed to load any TrueType font, using default")
            font = ImageFont.load_default()
        
        # Calculate layout from configuration with validation
        layout_config = config.get_layout_config()
        items_per_row = max(1, layout_config.get('items_per_row', 2))
        lozenge_width_margin = max(0, layout_config.get('lozenge_width_margin', 30))
        lozenge_height = max(20, layout_config.get('lozenge_height', 40))
        spacing = max(0, layout_config.get('spacing', 10))
        margin = max(0, layout_config.get('margin', 10))
        
        # Calculate lozenge width with bounds checking
        available_width = display.WIDTH - (2 * margin) - ((items_per_row - 1) * spacing)
        lozenge_width = max(50, available_width // items_per_row)
        
        # Draw lozenges with error handling for each item
        items_displayed = 0
        max_items = (display.HEIGHT - 2 * margin) // (lozenge_height + spacing) * items_per_row
        
        for i, item in enumerate(inventory[:max_items]):
            try:
                # Validate item format
                if not isinstance(item, (tuple, list)) or len(item) < 2:
                    logger.warning(f"Invalid inventory item format at index {i}: {item}")
                    continue
                
                item_name, quantity = item[0], item[1]
                
                # Validate item data
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
                y = margin + row * (lozenge_height + spacing)
                
                # Check if item fits on display
                if y + lozenge_height > display.HEIGHT - margin:
                    logger.warning(f"Item {item_name} doesn't fit on display, stopping")
                    break
                
                create_lozenge(draw, x, y, lozenge_width, lozenge_height,
                              item_name, quantity, font)
                items_displayed += 1
                
            except Exception as e:
                logger.error(f"Error drawing item {i}: {e}")
                continue
        
        # Update display with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                display.set_image(image)
                display.show()
                logger.info(f"Successfully updated display with {items_displayed} items")
                return True
            except Exception as e:
                logger.error(f"Error updating display (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5)  # Brief delay before retry
                else:
                    return False
    
    except Exception as e:
        logger.error(f"Unexpected error displaying inventory: {e}")
        logger.error(traceback.format_exc())
        return False

def cleanup_display(display):
    """Clean up display resources.
    
    Args:
        display: Display instance to clean up.
    """
    if not display:
        return
    
    try:
        # Clear the display
        if hasattr(display, 'clear'):
            display.clear()
            logger.info("Display cleared")
        
        # Release any resources
        if hasattr(display, 'cleanup'):
            display.cleanup()
            logger.info("Display resources cleaned up")
        elif hasattr(display, 'close'):
            display.close()
            logger.info("Display closed")
        
        logger.info("Display cleanup completed")
    except Exception as e:
        logger.error(f"Error during display cleanup: {e}")

def display_text(display, text, font_size=16):  # Larger default font size for WHAT
    """Display text on the Inky display with improved error handling."""
    if not display:
        logger.warning("No display available for text display")
        return False
    
    try:
        # Validate display object
        if not hasattr(display, 'WIDTH') or not hasattr(display, 'HEIGHT'):
            logger.error("Display object missing WIDTH or HEIGHT attributes")
            return False
        
        if not hasattr(display, 'set_image') or not hasattr(display, 'show'):
            logger.error("Display object missing set_image or show methods")
            return False
        
        # Validate text input
        if not text:
            text = " "  # Display blank if no text
        elif not isinstance(text, str):
            text = str(text)
        
        if Image is None:
            logger.critical("Critical Error: PIL.Image is None!")
            return False
        
        # Create a new image
        image = Image.new("P", (display.WIDTH, display.HEIGHT))
        draw = ImageDraw.Draw(image)
        
        # Load font with improved error handling
        font_config = config.get_font_config()
        font_path = font_config.get('path', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
        cfg_size = font_config.get('size', font_size)
        fallback_size = font_config.get('fallback_size', 12)
        desired_size = font_size or cfg_size
        
        # Validate font size
        if not isinstance(desired_size, (int, float)) or desired_size <= 0:
            desired_size = 16
            logger.warning(f"Invalid font size, using default: {desired_size}")
        
        font = None
        font_paths_to_try = [
            font_path,
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/System/Library/Fonts/Helvetica.ttc'  # macOS fallback
        ]
        
        for path in font_paths_to_try:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, int(desired_size))
                    logger.debug(f"Loaded font from {path}")
                    break
                except Exception as e:
                    logger.debug(f"Failed to load font from {path}: {e}")
                    continue
        
        if font is None:
            logger.warning("Failed to load any TrueType font, using default")
            font = ImageFont.load_default()
        
        # Handle text that might be too long
        max_width = display.WIDTH - 20  # Leave some margin
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
        line_height = font.size + 4
        total_height = len(text_lines) * line_height
        start_y = (display.HEIGHT - total_height) // 2
        
        # Draw each line
        for i, line in enumerate(text_lines):
            text_bbox = draw.textbbox((0, 0), line, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_x = (display.WIDTH - text_width) // 2
            text_y = start_y + i * line_height
            draw.text((text_x, text_y), line, fill='black', font=font)
        
        # Update display with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                display.set_image(image)
                display.show()
                logger.info(f"Successfully displayed text: {text[:50]}..." if len(text) > 50 else f"Successfully displayed text: {text}")
                return True
            except Exception as e:
                logger.error(f"Error updating display (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5)  # Brief delay before retry
                else:
                    return False
    
    except Exception as e:
        logger.error(f"Unexpected error displaying text: {e}")
        logger.error(traceback.format_exc())
        return False
