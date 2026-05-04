# Waveshare 3.97" e-Paper HAT+ display driver
# 800x480 resolution, 4-level grayscale, 3.5s refresh

import logging
import time
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Try to import the Waveshare library
WAVESHARE_AVAILABLE = False
epd_module = None
epd_driver_name = None
_epdconfig = None  # captured alongside the driver so cleanup can call module_exit
_waveshare_setup_attempted = False
_waveshare_setup_key = None


def _platform_probe_config(config_manager=None):
    if config_manager is None:
        return "/proc/device-tree/model", "raspberry pi"
    platform_config = config_manager.get_platform_config() or {}
    return (
        platform_config.get('raspberry_pi_model_file', '/proc/device-tree/model'),
        platform_config.get('required_pi_string', 'raspberry pi'),
    )


def _candidate_driver_modules(driver_name: str):
    try:
        waveshare_epd = __import__('waveshare_epd', fromlist=[driver_name])
        yield getattr(waveshare_epd, driver_name), f"waveshare_epd.{driver_name}"
    except (ImportError, AttributeError):
        pass

    try:
        yield __import__(driver_name), driver_name
    except ImportError:
        logger.debug(f"Driver {driver_name} not available via either import method")


def _driver_matches_display(test_module, label: str) -> bool:
    if not hasattr(test_module, 'EPD'):
        return False

    test_epd = test_module.EPD()
    if not hasattr(test_epd, 'width') or not hasattr(test_epd, 'height'):
        logger.info(f"Driver {label} found but no width/height attributes")
        return True

    logger.info(f"Testing driver {label}: {test_epd.width}x{test_epd.height}")
    if test_epd.width == 800 and test_epd.height == 480:
        logger.info(f"Found matching driver {label} for 800x480 display")
        return True
    if abs(test_epd.width - 800) <= 100 and abs(test_epd.height - 480) <= 100:
        logger.info(f"Found close driver {label} for display")
        return True
    return False


def _setup_waveshare_lib(config_manager=None):
    """Setup the Waveshare library path and import the module."""
    global WAVESHARE_AVAILABLE, epd_module, epd_driver_name, _epdconfig
    global _waveshare_setup_attempted, _waveshare_setup_key

    setup_key = _platform_probe_config(config_manager)
    if _waveshare_setup_attempted and _waveshare_setup_key == setup_key:
        return
    _waveshare_setup_attempted = True
    _waveshare_setup_key = setup_key
    WAVESHARE_AVAILABLE = False
    epd_module = None
    epd_driver_name = None
    _epdconfig = None

    from .platform_info import is_raspberry_pi
    model_file, required_string = setup_key
    if not is_raspberry_pi(model_file=model_file, required_string=required_string):
        logger.info("Not running on a Raspberry Pi, using mock display.")
        WAVESHARE_AVAILABLE = False
        return

    # Try multiple possible drivers for 3.97" display (800x480)
    # epd3in97 is the correct driver for 3.97" HAT+ (4-level grayscale)
    possible_drivers = ['epd3in97', 'epd7in5', 'epd4in2', 'epd3in7']
    epd_module = None
    epd_driver_name = None
    
    for driver_name in possible_drivers:
        for test_module, label in _candidate_driver_modules(driver_name):
            try:
                if not _driver_matches_display(test_module, label):
                    continue
                epd_module = test_module
                epd_driver_name = label
                WAVESHARE_AVAILABLE = True
                break
            except Exception as e:
                logger.debug(f"Error testing driver {label}: {e}")
                continue
        if WAVESHARE_AVAILABLE:
            break
    
    if epd_module is None:
        logger.error("No suitable Waveshare EPD driver found. Please run deploy.sh.")
        WAVESHARE_AVAILABLE = False
    elif hasattr(epd_module, 'epdconfig'):
        _epdconfig = epd_module.epdconfig
        logger.info("epdconfig module captured for cleanup")

def ensure_waveshare_lib(config_manager=None) -> bool:
    """Initialize Waveshare driver discovery on first use."""
    _setup_waveshare_lib(config_manager=config_manager)
    return WAVESHARE_AVAILABLE


class WaveshareDisplay:
    """Driver for Waveshare 3.97" e-Paper HAT+ display."""
    
    # Display specifications
    WIDTH = 800
    HEIGHT = 480
    
    # Grayscale levels (4-level) — must match driver's GRAY1-GRAY4 values
    # so getbuffer_4Gray maps them to the correct display levels
    WHITE = 0xFF      # driver GRAY1
    LIGHT_GRAY = 0xC0 # driver GRAY2
    DARK_GRAY = 0x80  # driver GRAY3
    BLACK = 0x00      # driver GRAY4
    
    def __init__(self, config_manager=None, show_test_pattern: bool = False):
        """Initialize the Waveshare display."""
        self._display = None
        self._initialized = False
        self._epd_instance = None
        self._is_mock = False
        self._show_test_pattern = show_test_pattern
        ensure_waveshare_lib(config_manager=config_manager)
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
        """Initialize the display hardware. Returns True on real hardware
        success; False if we fell back to a mock so callers can branch."""
        if self._initialized:
            return not self._is_mock

        if not self._epd_instance:
            logger.warning("Waveshare library not available, using mock display")
            self._display = MockDisplay()
            self._is_mock = True
            self._initialized = True
            return False
            
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

            if self._show_test_pattern:
                self._display_test_pattern(using_4gray)

            self._display = self._epd_instance
            self._initialized = True
            logger.info("Waveshare display initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Waveshare display: {e}")
            self._display = MockDisplay()
            self._is_mock = True
            self._initialized = True
            return False

    @staticmethod
    def _supports_4gray(display) -> bool:
        return (
            callable(getattr(display, 'display_4GRAY', None))
            and callable(getattr(display, 'getbuffer_4Gray', None))
        )

    def _display_test_pattern(self, using_4gray: bool) -> None:
        """Optional hardware smoke-test image for explicit diagnostics."""
        logger.info("Displaying test pattern...")
        test_image = Image.new("L", (self.WIDTH, self.HEIGHT), 255)
        draw = ImageDraw.Draw(test_image)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        except Exception:
            font = ImageFont.load_default()

        draw.text((50, 150), "FridgePinventory", fill=0, font=font)
        draw.text((50, 200), "4Gray Display", fill=85, font=font)
        draw.text((50, 250), "Initialized!", fill=170, font=font)

        if using_4gray and self._supports_4gray(self._epd_instance):
            buffer = self._epd_instance.getbuffer_4Gray(test_image)
            self._epd_instance.display_4GRAY(buffer)
        else:
            buffer = self._epd_instance.getbuffer(test_image.convert('1'))
            self._epd_instance.display(buffer)
    
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
            raise RuntimeError("No display available")
            
        try:
            # Ensure image is correct size
            if image.size != (self.WIDTH, self.HEIGHT):
                logger.warning(
                    f"Image size {image.size} doesn't match display size "
                    f"({self.WIDTH}, {self.HEIGHT})"
                )
                # Resize image to fit
                image = image.resize((self.WIDTH, self.HEIGHT), Image.LANCZOS)
            
            # Display the image based on mode
            logger.debug("Updating display with new image...")
            start_time = time.time()
            
            if image.mode == 'L' and self._supports_4gray(self._display):
                # Grayscale mode - use 4Gray display
                logger.debug("Using 4Gray display mode")
                self._display.display_4GRAY(self._display.getbuffer_4Gray(image))
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
            raise
    
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
                    
                # Call module_exit(cleanup=True) to release gpiozero resources.
                # sleep() already called module_exit() to close SPI/power; this
                # second call closes the gpiozero devices (LED/Button objects).
                if _epdconfig is not None:
                    _epdconfig.module_exit(cleanup=True)
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
    
    def display_4GRAY(self, buffer):
        logger.debug("Mock: 4-gray image displayed")

    def initialize(self):
        return True
    
    def sleep(self):
        logger.debug("Mock: Display sleeping")
    
    def Sleep(self):
        logger.debug("Mock: Display sleeping")
