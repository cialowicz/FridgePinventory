# Module for processing commands

import re
import logging
from typing import Tuple, Optional, Dict, List
from .item_normalizer import normalize_item_name
from .inventory_item import InventoryItem
from .config_manager import config
from .exceptions import CommandProcessingError

# Safe import of word2number
try:
    from word2number import w2n
    W2N_AVAILABLE = True
except ImportError:
    W2N_AVAILABLE = False
    logging.warning("word2number not available, number word parsing limited")

# Make spaCy optional and lazy-load the model when first needed
try:
    import spacy  # type: ignore
except Exception:
    spacy = None  # type: ignore

nlp = None

def _ensure_nlp(config_manager):
    """Attempt to load spaCy model once; return the model or None on failure."""
    global nlp
    if nlp is not None:
        return nlp
    if spacy is None:
        return None
    
    # Get NLP configuration
    nlp_config = config_manager.get_nlp_config()
    
    if not nlp_config.get('enable_spacy', True):
        logging.info("spaCy disabled in configuration, using rule-based parsing")
        nlp = None
        return None
    
    try:
        model_name = nlp_config.get('spacy_model', 'en_core_web_sm')
        nlp = spacy.load(model_name)
        logging.info(f"Successfully loaded spaCy model: {model_name}")
        return nlp
    except Exception as e:
        logging.warning(f"spaCy model '{nlp_config.get('spacy_model', 'en_core_web_sm')}' not available, falling back to rule-based parsing: {e}")
        nlp = None
        return None

def parse_quantity(text: str, config_manager) -> Optional[int]:
    """Parse a quantity from text, handling both numeric and word forms."""
    if not text:
        return None
    
    # Sanitize input
    text = text.strip()
    
    # Try direct numeric conversion first
    try:
        quantity = int(text)
        # Validate reasonable bounds
        if quantity < 0:
            logging.warning(f"Negative quantity parsed: {quantity}")
            return None
        if quantity > 10000:
            logging.warning(f"Unreasonably large quantity: {quantity}")
            return None
        return quantity
    except (ValueError, OverflowError):
        pass
    
    # Try word to number conversion
    try:
        # Get special quantities from configuration
        command_config = config_manager.get_command_config()
        special_quantities = command_config.get('special_quantities', {
            'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3,
            'four': 4, 'five': 5, 'six': 6, 'seven': 7,
            'eight': 8, 'nine': 9, 'ten': 10, 'dozen': 12
        })
        
        # First try our special quantities
        text_lower = text.lower()
        if text_lower in special_quantities:
            return special_quantities[text_lower]
        
        # Then try word2number if available
        if W2N_AVAILABLE:
            try:
                quantity = w2n.word_to_num(text)
                # Validate bounds
                if 0 <= quantity <= 10000:
                    return quantity
            except (ValueError, AttributeError):
                pass
    except Exception as e:
        logging.error(f"Error parsing quantity '{text}': {e}")
    
    return None

def interpret_command(command_text: str, config_manager) -> Tuple[Optional[str], Optional[InventoryItem]]:
    """
    Interpret a command from text input.
    Returns a tuple of (command_type, InventoryItem) for add/remove/set commands,
    or (None, None) if not recognized.
    """
    if not command_text:
        return None, None
    
    # Validate and sanitize input
    if not isinstance(command_text, str):
        logging.error(f"Invalid command type: {type(command_text)}")
        return None, None
    
    # Limit command length to prevent DoS
    if len(command_text) > 500:
        logging.warning(f"Command too long: {len(command_text)} characters")
        return None, None
        
    # Convert to lowercase for consistency
    command_text = command_text.lower().strip()
    
    # Remove dangerous characters
    command_text = re.sub(r'[;|&$`]', '', command_text)
    
    # Handle undo variations
    undo_words = ['undo', 'reverse', 'take back', 'cancel', 'revert']
    if any(word in command_text for word in undo_words):
        logging.info(f"Undo command detected: {command_text}")
        return "undo", None
    
    # Handle repeat variations (currently disabled)
    if any(word in command_text for word in ['repeat', 'again', 'same']):
        logging.info("Repeat command detected but currently disabled")
        return None, None
    
    # Determine command type with comprehensive pattern matching
    command_type = None
    model = _ensure_nlp(config_manager)
    
    try:
        if model is not None:
            doc = model(command_text)
            # Extended command recognition
            add_verbs = ['add', 'put', 'place', 'store', 'stock', 'insert']
            remove_verbs = ['remove', 'take', 'delete', 'use', 'consume', 'subtract']
            set_verbs = ['set', 'change', 'update', 'adjust', 'modify', 'correct']
            
            for token in doc:
                if token.lemma_ in add_verbs:
                    command_type = "add"
                    break
                elif token.lemma_ in remove_verbs:
                    command_type = "remove"
                    break
                elif token.lemma_ in set_verbs:
                    command_type = "set"
                    break
        else:
            # Enhanced regex patterns
            add_pattern = r"\b(add|put|place|store|stock|insert|got|bought|purchased)\b"
            remove_pattern = r"\b(remove|take|delete|use|used|consume|consumed|subtract|ate|finished)\b"
            set_pattern = r"\b(set|change|update|adjust|modify|correct|fix|have)\b"
            
            if re.search(add_pattern, command_text):
                command_type = "add"
            elif re.search(remove_pattern, command_text):
                command_type = "remove"
            elif re.search(set_pattern, command_text):
                command_type = "set"
    except Exception as e:
        logging.error(f"Error determining command type: {e}")
        # Fall back to basic pattern matching
        if "add" in command_text or "put" in command_text:
            command_type = "add"
        elif "remove" in command_text or "take" in command_text:
            command_type = "remove"
        elif "set" in command_text or "change" in command_text:
            command_type = "set"
    
    if not command_type:
        return None, None
    
    # Extract quantity and item with better error handling
    quantity = None
    item_name = None
    
    try:
        # For set commands, handle the special case of "to" vs "two"
        if command_type == "set":
            # Look for patterns like "set X to Y" or "set X Y"
            to_match = re.search(r"set\s+(.+?)\s+to\s+(\S+)", command_text)
            if to_match:
                item_name = to_match.group(1).strip()
                quantity_text = to_match.group(2).strip()
                quantity = parse_quantity(quantity_text, config_manager)
            else:
                # Try pattern without "to"
                set_match = re.search(r"set\s+(.+?)\s+(\d+|\w+)$", command_text)
                if set_match:
                    item_name = set_match.group(1).strip()
                    quantity = parse_quantity(set_match.group(2), config_manager)
        else:
            # For add/remove commands, look for quantity and item
            # Remove command word first
            text_without_command = re.sub(rf"\b{command_type}\b", "", command_text).strip()
            
            # Try to find quantity at the beginning
            words = text_without_command.split()
            if words:
                # Check first word for quantity
                first_quantity = parse_quantity(words[0], config_manager)
                if first_quantity is not None:
                    quantity = first_quantity
                    item_name = " ".join(words[1:])
                else:
                    # Check for quantity anywhere in the text
                    for i, word in enumerate(words):
                        parsed_quantity = parse_quantity(word, config_manager)
                        if parsed_quantity is not None:
                            quantity = parsed_quantity
                            # Item name is everything except the quantity word
                            item_words = words[:i] + words[i+1:]
                            item_name = " ".join(item_words)
                            break
                    
                    # If no quantity found, assume whole text is item name
                    if quantity is None:
                        item_name = text_without_command
        
        # Clean up item name
        if item_name:
            # Remove any remaining command words
            for cmd in ['add', 'remove', 'set', 'put', 'take', 'place', 'delete']:
                item_name = re.sub(rf"\b{cmd}\b", "", item_name).strip()
            
            # Remove extra whitespace
            item_name = " ".join(item_name.split())
        
        # Default to 1 if no quantity specified
        if quantity is None:
            quantity = 1
        
        # Validate final values
        if not item_name or len(item_name) < 1:
            logging.warning(f"Could not extract item name from: {command_text}")
            return command_type, None
        
        if quantity < 0 or quantity > 10000:
            logging.warning(f"Invalid quantity {quantity} for item {item_name}")
            return command_type, None
        
        # Normalize the item name and create InventoryItem
        try:
            item_name = normalize_item_name(item_name, config_manager)
            if item_name:  # normalize_item_name might return None
                return command_type, InventoryItem(item_name=item_name, quantity=quantity)
        except (ValueError, TypeError) as e:
            logging.error(f"Error creating inventory item: {e}")
            return command_type, None
    
    except Exception as e:
        logging.error(f"Error extracting quantity and item: {e}")
        return command_type, None
    
    return command_type, None
