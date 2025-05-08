# Module for managing the eInk display

import os
import logging
from math import ceil
from pi_inventory_system.inventory_db import get_inventory

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

# Initialize display-related variables
InkyWHAT = None
Image = None
ImageDraw = None
ImageFont = None

if is_raspberry_pi:
    try:
        logging.info("Attempting to import Inky display modules...")
        from inky.inky_uc8159 import InkyWHAT  # type: ignore
        from PIL import Image, ImageDraw, ImageFont
        logging.info("Successfully imported Inky display modules")
    except ImportError as e:
        logging.error(f"Failed to import Inky display modules: {e}")
        is_raspberry_pi = False
else:
    # Mock classes for non-Raspberry Pi testing
    logging.info("Using mock display classes for non-Raspberry Pi platform")
    class MockInkyWHAT:
        def __init__(self, color='yellow'):
            self.color = color
            self.WIDTH = 400
            self.HEIGHT = 300
        
        def set_image(self, image):
            pass
        
        def show(self):
            pass
    
    class MockImage:
        @staticmethod
        def new(mode, size, color):
            return None
    
    class MockImageDraw:
        @staticmethod
        def Draw(image):
            return None
    
    class MockImageFont:
        @staticmethod
        def truetype(font, size):
            return None
    
    InkyWHAT = MockInkyWHAT
    Image = MockImage
    ImageDraw = MockImageDraw
    ImageFont = MockImageFont

def is_display_supported():
    """Check if the display is supported on the current platform."""
    return is_raspberry_pi

def initialize_display():
    """Initialize the InkyWHAT display."""
    if not is_display_supported():
        logging.warning("Display not supported on this platform")
        return None
    
    try:
        logging.info("Initializing InkyWHAT display...")
        display = InkyWHAT('yellow')
        logging.info("Successfully initialized InkyWHAT display")
        return display
    except Exception as e:
        logging.error(f"Failed to initialize display: {e}")
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
    """Display the current inventory on the InkyWHAT display."""
    if not display:
        logging.warning("No display available for inventory display")
        return None
    
    try:
        # Get inventory data
        inventory = get_inventory()
        if not inventory:
            logging.info("No inventory to display")
            return None
        
        # Create a new image
        image = Image.new("P", (display.WIDTH, display.HEIGHT))
        draw = ImageDraw.Draw(image)
        
        # Load font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        except IOError:
            logging.warning("Failed to load DejaVuSans-Bold font, using default")
            font = ImageFont.load_default()
        
        # Calculate layout
        items_per_row = 2
        lozenge_width = (display.WIDTH - 30) // items_per_row
        lozenge_height = 40
        spacing = 10
        
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
        logging.info("Successfully updated display with inventory")
        return True
    
    except Exception as e:
        logging.error(f"Error displaying inventory: {e}")
        return None

def display_text(display, text, font_size=16):
    """Display text on the InkyWHAT display."""
    if not display:
        logging.warning("No display available for text display")
        return False
    
    try:
        # Create a new image
        image = Image.new("P", (display.WIDTH, display.HEIGHT))
        draw = ImageDraw.Draw(image)
        
        # Load font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except IOError:
            logging.warning("Failed to load DejaVuSans-Bold font, using default")
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
        logging.info("Successfully displayed text on display")
        return True
    
    except Exception as e:
        logging.error(f"Error displaying text: {e}")
        return False
