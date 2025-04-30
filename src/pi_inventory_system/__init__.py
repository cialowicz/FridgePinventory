"""
Pi Inventory System package
"""

__version__ = "0.1.0"

# Import and expose the main public API
from .inventory_db import (
    init_db,
    get_db,
    close_db,
    add_item,
    remove_item,
    set_item,
    get_inventory,
    undo_last_change,
    get_current_quantity
)

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

from .command_processor import (
    interpret_command,
    execute_command
)

from .audio_feedback import (
    play_feedback_sound,
    output_confirmation
)

__all__ = [
    # Database functions
    'init_db',
    'get_db',
    'close_db',
    'add_item',
    'remove_item',
    'set_item',
    'get_inventory',
    'undo_last_change',
    'get_current_quantity',
    
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
    
    # Command processing functions
    'interpret_command',
    'execute_command',
    
    # Audio feedback functions
    'play_feedback_sound',
    'output_confirmation'
] 