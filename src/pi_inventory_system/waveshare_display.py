# Waveshare 3.97" e-Paper HAT+ display driver
# 800x480 resolution, 4-level grayscale, 3.5s refresh

import os
import sys
import logging
import time
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Try to import the Waveshare library
WAVESHARE_AVAILABLE = False
epd = None

def _setup_waveshare_lib():
    """Setup the Waveshare library path and import the module."""
    global WAVESHARE_AVAILABLE, epd
    
    try:
        # Check if we're on a Raspberry Pi
        if not os.path.exists('/proc/device-tree/model'):
            logger.info("Not running on Raspberry Pi, using mock display")
            return False
            
        with open('/proc/device-tree/model', 'r') as f:
            if 'raspberry pi' not in f.read().lower():
                logger.info("Not running on Raspberry Pi, using mock display")
                return False
        
        # Try different import methods
        try:
            # Method 1: Try direct import if installed via pip
            from waveshare_epaper import epd3in97
            epd = epd3in97
            WAVESHARE_AVAILABLE = True
            logger.info("Successfully imported waveshare_epaper.epd3in97")
            return True
        except ImportError:
            pass
        
        # Method 2: Try adding the lib path for manual installation
        lib_paths = [
            '/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib',
            '/opt/e-Paper/RaspberryPi_JetsonNano/python/lib',
            os.path.join(os.path.dirname(__file__), 'lib'),
        ]
        
        for lib_path in lib_paths:
            if os.path.exists(lib_path):
                sys.path.insert(0, lib_path)
                try:
                    from waveshare_epaper import epd3in97
                    epd = epd3in97
                    WAVESHARE_AVAILABLE = True
                    logger.info(f"Successfully imported epd3in97 from {lib_path}")
                    return True
                except ImportError:
                    continue
        
        # Method 3: Try importing as a standalone module
        try:
            import epd3in97
            epd = epd3in97
            WAVESHARE_AVAILABLE = True
            logger.info("Successfully imported standalone epd3in97")
            return True
        except ImportError:
            pass
            
        logger.warning("Could not import Waveshare library, will use mock display")
        return False
        
    except Exception as e:
        logger.error(f"Error setting up Waveshare library: {e}")
        return False

# Initialize on module load
_setup_waveshare_lib()


class WaveshareDisplay:
    """Driver for Waveshare 3.97" e-Paper HAT+ display."""
    
    # Display specifications
    WIDTH = 800
    HEIGHT = 480
    
    # Grayscale levels (4-level)
    WHITE = 0xFF
    LIGHT_GRAY = 0xAA
    DARK_GRAY = 0x55
    BLACK = 0x00
    
    def __init__(self):
        """Initialize the Waveshare display."""
        self._display = None
        self._initialized = False
        
    def initialize(self):
        """Initialize the display hardware."""
        if self._initialized:
            return True
            
        if not WAVESHARE_AVAILABLE or not epd:
            logger.warning("Waveshare library not available, using mock display")
            self._display = MockDisplay()
            self._initialized = True
            return True
            
        try:
            # Create display instance
            self._display = epd.EPD()
            
            # Initialize the display
            logger.info("Initializing Waveshare 3.97\" display...")
            self._display.init()
            
            # Clear the display
            logger.info("Clearing display...")
            self._display.Clear()
            
            self._initialized = True
            logger.info("Waveshare display initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Waveshare display: {e}")
            # Fall back to mock display
            self._display = MockDisplay()
            self._initialized = True
            return False
    
    def clear(self):
        """Clear the display to white."""
        if not self._initialized:
            self.initialize()
            
        if self._display:
            try:
                self._display.Clear()
                logger.debug("Display cleared")
            except Exception as e:
                logger.error(f"Error clearing display: {e}")
    
    def display_image(self, image: Image.Image):
        """Display an image on the e-Paper.
        
        Args:
            image: PIL Image to display (should be 800x480)
        """
        if not self._initialized:
            self.initialize()
            
        if not self._display:
            logger.warning("No display available")
            return
            
        try:
            # Ensure image is correct size
            if image.size != (self.WIDTH, self.HEIGHT):
                logger.warning(f"Image size {image.size} doesn't match display size ({self.WIDTH}, {self.HEIGHT})")
                # Resize image to fit
                image = image.resize((self.WIDTH, self.HEIGHT), Image.LANCZOS)
            
            # Convert to grayscale if needed
            if image.mode != 'L':
                image = image.convert('L')
            
            # Display the image
            logger.debug("Updating display with new image...")
            start_time = time.time()
            
            if hasattr(self._display, 'display'):
                # For newer API
                self._display.display(self._display.getbuffer(image))
            else:
                # For older API
                self._display.display_4Gray(self._display.getbuffer_4Gray(image))
            
            elapsed = time.time() - start_time
            logger.info(f"Display updated in {elapsed:.1f} seconds")
            
        except Exception as e:
            logger.error(f"Error displaying image: {e}")
    
    def set_image(self, image: Image.Image):
        """Set image for display (compatibility with old API)."""
        self.display_image(image)
    
    def show(self):
        """Show the current buffer (compatibility with old API)."""
        # For Waveshare, set_image already displays
        pass
    
    def set_border(self, color):
        """Set border color (compatibility method)."""
        # Waveshare doesn't have a separate border setting
        pass
    
    def cleanup(self):
        """Clean up display resources."""
        if self._display and self._initialized:
            try:
                # Put display to sleep to save power
                if hasattr(self._display, 'sleep'):
                    self._display.sleep()
                    logger.info("Display put to sleep")
                elif hasattr(self._display, 'Sleep'):
                    self._display.Sleep()
                    logger.info("Display put to sleep")
            except Exception as e:
                logger.error(f"Error during display cleanup: {e}")


class MockDisplay:
    """Mock display for testing without hardware."""
    
    WIDTH = 800
    HEIGHT = 480
    WHITE = 0xFF
    BLACK = 0x00
    
    def __init__(self):
        logger.info("Using mock Waveshare display")
    
    def init(self):
        pass
    
    def Clear(self):
        logger.debug("Mock: Display cleared")
    
    def getbuffer(self, image):
        return []
    
    def getbuffer_4Gray(self, image):
        return []
    
    def display(self, buffer):
        logger.debug("Mock: Image displayed")
    
    def display_4Gray(self, buffer):
        logger.debug("Mock: 4-gray image displayed")
    
    def sleep(self):
        logger.debug("Mock: Display sleeping")
    
    def Sleep(self):
        logger.debug("Mock: Display sleeping")
