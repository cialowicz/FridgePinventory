"""
Pi Inventory System package
"""

__version__ = "0.1.0"

# Import and expose the main public API
from .database_manager import db_manager
from .inventory_controller import InventoryController

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

from .audio_feedback import (
    play_feedback_sound,
    output_confirmation
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
    
    # Audio feedback functions
    'play_feedback_sound',
    'output_confirmation'
] 
