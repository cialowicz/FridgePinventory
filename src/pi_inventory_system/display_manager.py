# Module for managing the eInk display

import platform
from math import ceil
from pi_inventory_system.inventory_db import get_inventory

def _is_raspberry_pi():
    """Check if we're running on a Raspberry Pi."""
    return platform.system() == 'Linux' and platform.machine().startswith('arm')

# Initialize display support
is_raspberry_pi = _is_raspberry_pi()

if is_raspberry_pi:
    try:
        from inky.inky_uc8159 import InkyWHAT  # type: ignore
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        is_raspberry_pi = False
        InkyWHAT = None
        Image = None
        ImageDraw = None
        ImageFont = None
else:
    # Mock classes for non-Raspberry Pi testing
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
    return _is_raspberry_pi()

def initialize_display():
    """Initialize the InkyWHAT display."""
    if not is_display_supported():
        return None
    
    try:
        display = InkyWHAT('yellow')
        return display
    except Exception:
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
        return None
    
    try:
        # Get inventory data
        inventory = get_inventory()
        if not inventory:
            return None
        
        # Create a new image
        image = Image.new("P", (display.WIDTH, display.HEIGHT))
        draw = ImageDraw.Draw(image)
        
        # Load font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        except IOError:
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
        return True
    
    except Exception:
        return None
