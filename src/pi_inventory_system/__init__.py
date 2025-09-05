"""
Pi Inventory System package
"""

__version__ = "0.1.0"

# Import and expose the main public API
from .config_manager import get_default_config_manager
from .database_manager import create_database_manager
from .inventory_controller import InventoryController
from .audio_feedback_manager import AudioFeedbackManager

# Initialize default managers
default_config_manager = get_default_config_manager()
db_manager = create_database_manager(default_config_manager)

from .display_manager import (
    initialize_display,
    display_inventory,
    is_display_supported
)

from .motion_sensor import (
    detect_motion,
    is_motion_sensor_supported
)

from .voice_recognition import (
    recognize_speech_from_mic
)

from .item_normalizer import (
    normalize_item_name,
    get_item_synonyms
)

from .inventory_item import (
    InventoryItem
)

from .command_processor import (
    interpret_command
)

__all__ = [
    # Singletons and Controllers
    'db_manager',
    'InventoryController',
    
    # Display functions
    'initialize_display',
    'display_inventory',
    'is_display_supported',
    
    # Motion sensor functions
    'detect_motion',
    'is_motion_sensor_supported',
    
    # Voice recognition functions
    'recognize_speech_from_mic',
    
    # Item normalization functions
    'normalize_item_name',
    'get_item_synonyms',
    
    # Data classes
    'InventoryItem',
    
    # Command processing functions
    'interpret_command',
]
