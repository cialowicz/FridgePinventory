# Module for managing the eInk display

import os
import logging
import traceback

# Configure logging for this module
logger = logging.getLogger(__name__)

from math import ceil
from pi_inventory_system.inventory_db import get_inventory

INKY_AVAILABLE = False

def _is_raspberry_pi():
    """Check if we're running on a Raspberry Pi."""
    # Check for Raspberry Pi specific files
    if os.path.exists('/proc/device-tree/model'):
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().lower()
            return 'raspberry pi' in model
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
    # Determine border color based on quantity
    border_color = 'yellow' if quantity <= 2 else 'black'
    
    # Draw the lozenge shape
    draw.rectangle([(x, y), (x + width, y + height)], fill='white', outline=border_color)
    
    # Add item name and quantity
    text = f"{item_name}: {quantity}"
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    text_x = x + (width - text_width) // 2
    text_y = y + (height - text_height) // 2
    
    draw.text((text_x, text_y), text, fill='black', font=font)

def display_inventory(display):
    """Display the current inventory on the Inky display."""
    if not display:
        logger.warning("No display available for inventory display")
        return None
    
    try:
        # Get inventory data
        inventory = get_inventory()
        if not inventory:
            logger.info("No inventory to display")
            return None
        
        # Create a new image
        image = Image.new("P", (display.WIDTH, display.HEIGHT))
        draw = ImageDraw.Draw(image)
        
        # Load font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)  # Larger font for WHAT
        except IOError:
            logger.warning("Failed to load DejaVuSans-Bold font, using default")
            font = ImageFont.load_default()
        
        # Calculate layout
        items_per_row = 2  # WHAT is wider, so we can fit two items per row
        lozenge_width = (display.WIDTH - 30) // items_per_row  # Leave margins
        lozenge_height = 40  # Taller for WHAT
        spacing = 10  # More spacing for WHAT
        
        # Draw lozenges
        for i, item in enumerate(inventory):
            row = i // items_per_row
            col = i % items_per_row
            
            x = 10 + col * (lozenge_width + spacing)
            y = 10 + row * (lozenge_height + spacing)
            
            create_lozenge(draw, x, y, lozenge_width, lozenge_height,
                          item.item_name, item.quantity, font)
        
        # Update display
        display.set_image(image)
        display.show()
        logger.info("Successfully updated display with inventory")
        return True
    
    except Exception as e:
        logger.error(f"Error displaying inventory: {e}")
        return None

def display_text(display, text, font_size=16):  # Larger default font size for WHAT
    """Display text on the Inky display."""
    if not display:
        logger.warning("No display available for text display")
        return False
    
    try:

        if Image is None:
            logger.critical("Critical Error: PIL.Image is None immediately after import!")
            return False
        
        # Create a new image
        image = Image.new("P", (display.WIDTH, display.HEIGHT))
        draw = ImageDraw.Draw(image)
        
        # Load font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except IOError:
            logger.warning("Failed to load DejaVuSans-Bold font, using default")
            font = ImageFont.load_default()
        
        # Calculate text position
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        text_x = (display.WIDTH - text_width) // 2
        text_y = (display.HEIGHT - text_height) // 2
        
        # Draw text
        draw.text((text_x, text_y), text, fill='black', font=font)
        
        # Update display
        display.set_image(image)
        display.show()
        logger.info("Successfully displayed text on display")
        return True
    
    except Exception as e:
        logger.error(f"Error displaying text: {e}")
        return False
