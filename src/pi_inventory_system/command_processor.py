# Module for processing commands

import re
import logging
from typing import Tuple, Optional, Dict, List
from word2number import w2n
from .database_manager import db_manager
from .item_normalizer import normalize_item_name
from .inventory_item import InventoryItem
from .config_manager import config

# Make spaCy optional and lazy-load the model when first needed
try:
    import spacy  # type: ignore
except Exception:
    spacy = None  # type: ignore

nlp = None

def _ensure_nlp():
    """Attempt to load spaCy model once; return the model or None on failure."""
    global nlp
    if nlp is not None:
        return nlp
    if spacy is None:
        return None
    try:
        nlp = spacy.load("en_core_web_sm")  # Requires separate model install
        return nlp
    except Exception as e:
        logging.warning(f"spaCy model not available, falling back to rule-based parsing: {e}")
        nlp = None
        return None

def parse_quantity(text: str) -> Optional[int]:
    """Parse a quantity from text, handling both numeric and word forms."""
    try:
        # Try direct numeric conversion first
        return int(text)
    except ValueError:
        # Try word to number conversion
        try:
            # Get special quantities from configuration
            command_config = config.get_command_config()
            special_quantities = command_config.get('special_quantities', {})
            
            # First try our special quantities
            if text.lower() in special_quantities:
                return special_quantities[text.lower()]
            # Then try word2number for other number words
            return w2n.word_to_num(text)
        except ValueError:
            return None

def interpret_command(command_text: str) -> Tuple[Optional[str], Optional[InventoryItem]]:
    """
    Interpret a command from text input.
    Returns a tuple of (command_type, InventoryItem) for add/remove/set commands,
    or (None, None) if not recognized.
    """
    if not command_text:
        return None, None
        
    # Convert to lowercase for consistency
    command_text = command_text.lower().strip()
    
    # Handle undo variations
    if any(word in command_text for word in ['undo', 'reverse', 'take back', 'cancel']):
        return "undo", None
    
    # Handle repeat variations
    if any(word in command_text for word in ['repeat', 'again', 'same']):
        # NOTE: Repeat functionality is temporarily disabled pending state management refactor.
        # The command history is now in the InventoryController.
        return None, None
    
    # Determine command type using spaCy if available, otherwise simple regex fallback
    command_type = None
    model = _ensure_nlp()
    if model is not None:
        doc = model(command_text)
        if any(token.lemma_ in ['add', 'put', 'place'] for token in doc):
            command_type = "add"
        elif any(token.lemma_ in ['remove', 'take', 'delete'] for token in doc):
            command_type = "remove"
        elif any(token.lemma_ in ['set', 'change', 'update'] for token in doc):
            command_type = "set"
    else:
        if re.search(r"\b(add|put|place)\b", command_text):
            command_type = "add"
        elif re.search(r"\b(remove|take|delete)\b", command_text):
            command_type = "remove"
        elif re.search(r"\b(set|change|update)\b", command_text):
            command_type = "set"
    
    if not command_type:
        return None, None
    
    # Extract quantity and item
    quantity = None
    item_name = None
    
    # For set commands, handle the special case of "to" vs "two"
    if command_type == "set":
        # Look for the word after "to"
        to_index = command_text.find(" to ")
        if to_index != -1:
            item_name = command_text[:to_index].strip()
            # Remove the command type from the item name
            item_name = item_name.replace(command_type, "").strip()
            # Look for the quantity after "to"
            quantity_text = command_text[to_index + 4:].strip()
            quantity = parse_quantity(quantity_text)
    else:
        # For add/remove commands, look for number words or numeric values
        words = command_text.split()
        for i, word in enumerate(words):
            # Try to parse the word as a quantity
            parsed_quantity = parse_quantity(word)
            if parsed_quantity is not None:
                quantity = parsed_quantity
                # Join the remaining words as the item name
                item_name = " ".join(words[i+1:])
                # Remove the command type from the item name
                item_name = item_name.replace(command_type, "").strip()
                break
    
    # Default to 1 if no quantity specified
    if quantity is None:
        quantity = 1
    
    # Normalize the item name and create InventoryItem
    if item_name:
        item_name = normalize_item_name(item_name)
        return command_type, InventoryItem(item_name=item_name, quantity=quantity)
    
    return None, None
