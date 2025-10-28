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
epd_module = None
epd_driver_name = None

def _setup_waveshare_lib():
    """Setup the Waveshare library path and import the module."""
    global WAVESHARE_AVAILABLE, epd_module, epd_driver_name
    
    try:
        # Check if we're on a Raspberry Pi
        if not os.path.exists('/proc/device-tree/model'):
            logger.info("Not running on Raspberry Pi, using mock display")
            return False
            
        with open('/proc/device-tree/model', 'r') as f:
            if 'raspberry pi' not in f.read().lower():
                logger.info("Not running on a Raspberry Pi, using mock display.")
                WAVESHARE_AVAILABLE = False
                return
    except FileNotFoundError:
        logger.info("Not running on a Raspberry Pi (or unable to detect), using mock display.")
        WAVESHARE_AVAILABLE = False
        return

    # Try multiple possible drivers for 3.97" display (800x480)
    # epd3in97 is the correct driver for 3.97" HAT+ (4-level grayscale)
    possible_drivers = ['epd3in97', 'epd7in5', 'epd4in2', 'epd3in7']
    epd_module = None
    epd_driver_name = None
    
    for driver_name in possible_drivers:
        # Try importing from waveshare_epd package first (preferred method)
        try:
            waveshare_epd = __import__('waveshare_epd', fromlist=[driver_name])
            test_module = getattr(waveshare_epd, driver_name)
            # Check if this driver has the right resolution for our 3.97" display
            if hasattr(test_module, 'EPD'):
                test_epd = test_module.EPD()
                if hasattr(test_epd, 'width') and hasattr(test_epd, 'height'):
                    logger.info(f"Testing driver waveshare_epd.{driver_name}: {test_epd.width}x{test_epd.height}")
                    if test_epd.width == 800 and test_epd.height == 480:
                        logger.info(f"Found matching driver waveshare_epd.{driver_name} for 800x480 display")
                        epd_module = test_module
                        epd_driver_name = f"waveshare_epd.{driver_name}"
                        WAVESHARE_AVAILABLE = True
                        break
                    elif abs(test_epd.width - 800) <= 100 and abs(test_epd.height - 480) <= 100:
                        logger.info(f"Found close driver waveshare_epd.{driver_name} for display")
                        epd_module = test_module
                        epd_driver_name = f"waveshare_epd.{driver_name}"
                        WAVESHARE_AVAILABLE = True
                        break
                else:
                    logger.info(f"Driver waveshare_epd.{driver_name} found but no width/height attributes")
                    epd_module = test_module
                    epd_driver_name = f"waveshare_epd.{driver_name}"
                    WAVESHARE_AVAILABLE = True
                    break
        except (ImportError, AttributeError):
            # Fallback: try importing directly (may fail for drivers with relative imports)
            try:
                test_module = __import__(driver_name)
                if hasattr(test_module, 'EPD'):
                    test_epd = test_module.EPD()
                    if hasattr(test_epd, 'width') and hasattr(test_epd, 'height'):
                        logger.info(f"Testing driver {driver_name}: {test_epd.width}x{test_epd.height}")
                        if test_epd.width == 800 and test_epd.height == 480:
                            logger.info(f"Found matching driver {driver_name} for 800x480 display")
                            epd_module = test_module
                            epd_driver_name = driver_name
                            WAVESHARE_AVAILABLE = True
                            break
                        elif abs(test_epd.width - 800) <= 100 and abs(test_epd.height - 480) <= 100:
                            logger.info(f"Found close driver {driver_name} for display")
                            epd_module = test_module
                            epd_driver_name = driver_name
                            WAVESHARE_AVAILABLE = True
                            break
                    else:
                        logger.info(f"Driver {driver_name} found but no width/height attributes")
                        epd_module = test_module
                        epd_driver_name = driver_name
                        WAVESHARE_AVAILABLE = True
                        break
            except ImportError:
                logger.debug(f"Driver {driver_name} not available via either import method")
                continue
        except Exception as e:
            logger.debug(f"Error testing driver {driver_name}: {e}")
            continue
    
    if epd_module is None:
        logger.error("No suitable Waveshare EPD driver found. Please run deploy.sh.")
        WAVESHARE_AVAILABLE = False

# Check for the library when the module is loaded.
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
        self._epd_instance = None
        if WAVESHARE_AVAILABLE and epd_module:
            try:
                logger.info(f"Using Waveshare driver: {epd_driver_name}")
                self._epd_instance = epd_module.EPD()
                self.width = getattr(self._epd_instance, 'width', self.WIDTH)
                self.height = getattr(self._epd_instance, 'height', self.HEIGHT)
                logger.info(f"Display dimensions: {self.width}x{self.height}")
                self.init_display()
            except Exception as e:
                logger.error(f"Failed to initialize Waveshare display: {e}")
                self._epd_instance = None
        else:
            logger.warning("Waveshare library not available. Using mock display.")
            self.width = self.WIDTH
            self.height = self.HEIGHT
    
    def initialize(self):
        """Backwards-compatible initializer that mirrors init_display."""
        return self.init_display()
    
    def init_display(self):
        """Initialize the display hardware."""
        if self._initialized:
            return True
            
        if not self._epd_instance:
            logger.warning("Waveshare library not available, using mock display")
            self._display = MockDisplay()
            self._initialized = True
            return True
            
        try:
            logger.info("Initializing Waveshare 3.97\" display...")
            using_4gray = False

            if hasattr(self._epd_instance, 'init_4GRAY'):
                logger.info("Calling init_4GRAY() for 4-level grayscale waveform")
                init_result = self._epd_instance.init_4GRAY()
                using_4gray = True
            else:
                init_result = self._epd_instance.init()

            if init_result == -1:
                raise RuntimeError("EPD init routine returned error code -1")

            logger.info("Clearing display...")
            self._epd_instance.Clear()

            logger.info("Displaying test pattern...")
            from PIL import Image, ImageDraw, ImageFont
            test_image = Image.new("L", (self.WIDTH, self.HEIGHT), 255)  # Grayscale white background
            draw = ImageDraw.Draw(test_image)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            except Exception:
                font = ImageFont.load_default()

            draw.text((50, 150), "FridgePinventory", fill=0, font=font)  # Black
            draw.text((50, 200), "4Gray Display", fill=85, font=font)   # Dark gray
            draw.text((50, 250), "Initialized!", fill=170, font=font)   # Light gray

            if using_4gray and hasattr(self._epd_instance, 'display_4Gray'):
                buffer = self._epd_instance.getbuffer_4Gray(test_image)
                self._epd_instance.display_4Gray(buffer)
            else:
                buffer = self._epd_instance.getbuffer(test_image.convert('1'))
                self._epd_instance.display(buffer)

            self._display = self._epd_instance
            self._initialized = True
            logger.info("Waveshare display initialized successfully with test pattern")
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
            self.init_display()
            
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
            self.init_display()
            
        if not self._display:
            logger.warning("No display available")
            return
            
        try:
            # Ensure image is correct size
            if image.size != (self.WIDTH, self.HEIGHT):
                logger.warning(f"Image size {image.size} doesn't match display size ({self.WIDTH}, {self.HEIGHT})")
                # Resize image to fit
                image = image.resize((self.WIDTH, self.HEIGHT), Image.LANCZOS)
            
            # Display the image based on mode
            logger.debug("Updating display with new image...")
            start_time = time.time()
            
            if image.mode == 'L':
                # Grayscale mode - use 4Gray display
                logger.debug("Using 4Gray display mode")
                self._display.display_4Gray(self._display.getbuffer_4Gray(image))
            else:
                # 1-bit or other mode - convert to 1-bit and use basic display
                if image.mode != '1':
                    logger.debug("Converting image to 1-bit mode")
                    image = image.convert('1')
                logger.debug("Using basic display mode")
                self._display.display(self._display.getbuffer(image))
            
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
    
    def init_fast(self):
        """Initialize display for fast refresh mode."""
        if self._display and hasattr(self._display, 'init_Fast'):
            try:
                self._display.init_Fast()
                logger.info("Display initialized in fast mode")
            except Exception as e:
                logger.error(f"Error initializing fast mode: {e}")
    
    def init_4gray(self):
        """Initialize display for 4-level grayscale mode."""
        if self._display and hasattr(self._display, 'init_4GRAY'):
            try:
                self._display.init_4GRAY()
                logger.info("Display initialized in 4Gray mode")
            except Exception as e:
                logger.error(f"Error initializing 4Gray mode: {e}")
    
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
                    
                # Call module exit for proper cleanup (like in example)
                if hasattr(self._display, 'epdconfig'):
                    self._display.epdconfig.module_exit(cleanup=True)
                    logger.debug("EPD module cleanup called")
                    
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

    def initialize(self):
        return True
    
    def sleep(self):
        logger.debug("Mock: Display sleeping")
    
    def Sleep(self):
        logger.debug("Mock: Display sleeping")
