"""Voice-command interpretation: text -> (command_type, InventoryItem)."""

import logging
import re
from typing import Optional, Tuple

from .inventory_item import InventoryItem
from .item_normalizer import normalize_item_name

try:
    from word2number import w2n
    W2N_AVAILABLE = True
except ImportError:
    W2N_AVAILABLE = False
    logging.warning("word2number not available, number word parsing limited")

try:
    import spacy  # type: ignore
except Exception:
    spacy = None  # type: ignore

_nlp = None
_nlp_load_attempted = False

UNDO_WORDS = ('undo', 'reverse', 'take back', 'cancel', 'revert')
ADD_VERBS = ('add', 'put', 'place', 'store', 'stock', 'insert', 'got', 'bought', 'purchased')
REMOVE_VERBS = ('remove', 'take', 'delete', 'use', 'used', 'consume', 'consumed',
                'subtract', 'ate', 'finished')
SET_VERBS = ('set', 'change', 'update', 'adjust', 'modify', 'correct', 'fix')
COMMAND_WORDS_TO_STRIP = ('add', 'remove', 'set', 'put', 'take', 'place', 'delete')

DEFAULT_QUANTITIES = {
    'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3,
    'four': 4, 'five': 5, 'six': 6, 'seven': 7,
    'eight': 8, 'nine': 9, 'ten': 10, 'dozen': 12,
}

MAX_COMMAND_LEN = 500
MAX_QUANTITY = 10000


def _ensure_nlp(config_manager):
    """Load spaCy lazily; cache the result so we only attempt once."""
    global _nlp, _nlp_load_attempted
    if _nlp_load_attempted:
        return _nlp
    _nlp_load_attempted = True

    if spacy is None:
        return None
    nlp_config = config_manager.get_nlp_config()
    if not nlp_config.get('enable_spacy', True):
        logging.info("spaCy disabled in configuration, using rule-based parsing")
        return None
    model_name = nlp_config.get('spacy_model', 'en_core_web_sm')
    try:
        _nlp = spacy.load(model_name)
        logging.info(f"Loaded spaCy model: {model_name}")
    except Exception as e:
        logging.warning(f"spaCy model '{model_name}' unavailable, falling back: {e}")
        _nlp = None
    return _nlp


def parse_quantity(text: str, config_manager) -> Optional[int]:
    """Parse a quantity from text, accepting digits and number-words.
    Returns None for invalid, negative, or out-of-range values."""
    if not text:
        return None
    text = text.strip()

    try:
        quantity = int(text)
    except (ValueError, OverflowError):
        quantity = None

    if quantity is None:
        text_lower = text.lower()
        special = (config_manager.get_command_config().get('special_quantities')
                   or DEFAULT_QUANTITIES)
        if text_lower in special:
            quantity = special[text_lower]
        elif W2N_AVAILABLE:
            try:
                quantity = w2n.word_to_num(text_lower)
            except (ValueError, AttributeError):
                quantity = None

    if quantity is None:
        return None
    if quantity < 0 or quantity > MAX_QUANTITY:
        logging.warning(f"Quantity out of range: {quantity}")
        return None
    return quantity


def _classify_verb(command_text: str, config_manager) -> Optional[str]:
    """Decide whether the user said add / remove / set / undo / nothing.
    Tries spaCy lemmas first, falls back to keyword regex."""
    if any(word in command_text for word in UNDO_WORDS):
        return "undo"

    model = _ensure_nlp(config_manager)
    if model is not None:
        try:
            doc = model(command_text)
            for token in doc:
                if token.lemma_ in ADD_VERBS:
                    return "add"
                if token.lemma_ in REMOVE_VERBS:
                    return "remove"
                if token.lemma_ in SET_VERBS:
                    return "set"
        except Exception as e:
            logging.error(f"spaCy classification failed: {e}")

    for verb_set, label in ((ADD_VERBS, "add"), (REMOVE_VERBS, "remove"), (SET_VERBS, "set")):
        if re.search(rf"\b({'|'.join(verb_set)})\b", command_text):
            return label
    return None


def _extract_set_arguments(command_text: str, config_manager):
    """Parse 'set X to Y' or 'set X Y'. Returns (item_name, quantity) or (None, None)."""
    match = re.search(r"set\s+(.+?)\s+to\s+(\S+)\s*$", command_text)
    if match:
        return match.group(1).strip(), parse_quantity(match.group(2), config_manager)
    match = re.search(r"set\s+(.+?)\s+(\S+)\s*$", command_text)
    if match:
        return match.group(1).strip(), parse_quantity(match.group(2), config_manager)
    return None, None


def _extract_add_remove_arguments(command_text: str, command_type: str, config_manager):
    """Strip the command verb and pull the first quantity-token + item name."""
    text = re.sub(rf"\b{command_type}\b", "", command_text).strip()
    words = text.split()
    if not words:
        return None, None

    first = parse_quantity(words[0], config_manager)
    if first is not None:
        return " ".join(words[1:]) or None, first
    for i, word in enumerate(words):
        qty = parse_quantity(word, config_manager)
        if qty is not None:
            item_words = words[:i] + words[i + 1:]
            return " ".join(item_words) or None, qty
    return text, None


def _scrub_item_name(item_name: str) -> str:
    for cmd in COMMAND_WORDS_TO_STRIP:
        item_name = re.sub(rf"\b{cmd}\b", "", item_name)
    return " ".join(item_name.split())


def interpret_command(command_text: str, config_manager) -> Tuple[Optional[str], Optional[InventoryItem]]:
    """Interpret a voice command. Returns (command_type, InventoryItem) or (None, None)."""
    if not command_text or not isinstance(command_text, str):
        return None, None
    if len(command_text) > MAX_COMMAND_LEN:
        logging.warning(f"Command too long: {len(command_text)} characters")
        return None, None

    command_text = command_text.lower().strip()
    command_type = _classify_verb(command_text, config_manager)
    if command_type is None:
        return None, None
    if command_type == "undo":
        logging.info(f"Undo command detected: {command_text}")
        return "undo", None

    if command_type == "set":
        item_name, quantity = _extract_set_arguments(command_text, config_manager)
    else:
        item_name, quantity = _extract_add_remove_arguments(command_text, command_type, config_manager)

    if item_name:
        item_name = _scrub_item_name(item_name)
    if quantity is None:
        quantity = 1
    if not item_name:
        logging.warning(f"Could not extract item name from: {command_text}")
        return command_type, None
    if quantity < 0 or quantity > MAX_QUANTITY:
        logging.warning(f"Invalid quantity {quantity} for item {item_name}")
        return command_type, None

    normalized = normalize_item_name(item_name, config_manager) or item_name
    try:
        return command_type, InventoryItem(item_name=normalized, quantity=quantity)
    except (ValueError, TypeError) as e:
        logging.error(f"Error creating inventory item: {e}")
        return command_type, None
