"""Voice-command interpretation: text -> (command_type, InventoryItem)."""

import logging
import re
import threading
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
_nlp_lock = threading.Lock()

UNDO_WORDS = ('undo', 'reverse', 'take back', 'cancel', 'revert')
ADD_VERBS = ('add', 'put', 'place', 'store', 'stock', 'insert', 'got', 'bought', 'purchased')
REMOVE_VERBS = ('remove', 'take', 'delete', 'use', 'used', 'consume', 'consumed',
                'subtract', 'ate', 'finished')
SET_VERBS = ('set', 'change', 'update', 'adjust', 'modify', 'correct', 'fix')
COMMAND_WORDS_TO_STRIP = tuple(sorted(
    set(ADD_VERBS + REMOVE_VERBS + SET_VERBS),
    key=len,
    reverse=True,
))
# Pre-compiled alternation: one re.sub per item-name scrub instead of N.
_COMMAND_WORDS_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in COMMAND_WORDS_TO_STRIP) + r")\b"
)
ITEM_FILLER_WORDS = {'of', 'the'}

DEFAULT_QUANTITIES = {
    'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3,
    'four': 4, 'five': 5, 'six': 6, 'seven': 7,
    'eight': 8, 'nine': 9, 'ten': 10, 'dozen': 12,
}

MAX_COMMAND_LEN = 500
MAX_QUANTITY = 10000


def _ensure_nlp(config_manager):
    """Load spaCy lazily. Permanent skips (no spacy installed, disabled in
    config) latch via _nlp_load_attempted; transient OSError from a partially
    installed model leaves the flag False so a later restart of the load
    succeeds without restarting the process."""
    global _nlp, _nlp_load_attempted
    if _nlp_load_attempted:
        return _nlp

    with _nlp_lock:
        if _nlp_load_attempted:
            return _nlp

        if spacy is None:
            _nlp_load_attempted = True
            return None
        nlp_config = config_manager.get_nlp_config()
        if not nlp_config.get('enable_spacy', True):
            logging.info("spaCy disabled in configuration, using rule-based parsing")
            _nlp_load_attempted = True
            return None
        model_name = nlp_config.get('spacy_model', 'en_core_web_sm')
        try:
            _nlp = spacy.load(model_name)
            logging.info(f"Loaded spaCy model: {model_name}")
            _nlp_load_attempted = True
        except OSError as e:
            logging.warning(
                f"spaCy model '{model_name}' load failed (transient): {e}; "
                "will retry on next command")
            _nlp = None
        except Exception as e:
            logging.warning(f"spaCy model '{model_name}' unavailable, falling back: {e}")
            _nlp = None
            _nlp_load_attempted = True
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


def _strip_leading_verb(command_text: str, verbs) -> str:
    """Remove the matched command verb while preserving the item phrase."""
    verb_pattern = "|".join(re.escape(verb) for verb in sorted(verbs, key=len, reverse=True))
    return re.sub(rf"^\s*(?:{verb_pattern})\b\s*", "", command_text, count=1).strip()


def _clean_item_words(words):
    return [word for word in words if word not in ITEM_FILLER_WORDS]


def _parse_quantity_words(words, config_manager):
    """Return (quantity, consumed_words) for a leading quantity phrase."""
    if not words:
        return None, 0

    first = parse_quantity(words[0], config_manager)
    if len(words) > 1 and words[1] == "dozen":
        if words[0] in ("a", "an", "one"):
            return 12, 2
        if first is not None:
            return first * 12, 2

    if first is not None:
        return first, 1

    if len(words) > 1 and words[0] in ("a", "an"):
        second = parse_quantity(words[1], config_manager)
        if second is not None:
            return second, 2

    for end in range(min(4, len(words)), 1, -1):
        quantity = parse_quantity(" ".join(words[:end]), config_manager)
        if quantity is not None:
            return quantity, end

    return None, 0


def _extract_set_arguments(command_text: str, config_manager):
    """Parse 'set X to Y' or 'set X Y'. Returns (item_name, quantity) or (None, None)."""
    text = _strip_leading_verb(command_text, SET_VERBS)
    match = re.search(r"(.+?)\s+to\s+(.+?)\s*$", text)
    if match:
        return match.group(1).strip(), parse_quantity(match.group(2), config_manager)
    match = re.search(r"(.+?)\s+(\S+)\s*$", text)
    if match:
        return match.group(1).strip(), parse_quantity(match.group(2), config_manager)
    return None, None


def _extract_add_remove_arguments(command_text: str, command_type: str, config_manager):
    """Strip the command verb and pull the first quantity-token + item name."""
    verbs = ADD_VERBS if command_type == "add" else REMOVE_VERBS
    text = _strip_leading_verb(command_text, verbs)
    words = text.split()
    if not words:
        return None, None

    quantity, consumed = _parse_quantity_words(words, config_manager)
    if quantity is not None:
        item_words = _clean_item_words(words[consumed:])
        return " ".join(item_words) or None, quantity

    for i, word in enumerate(words):
        qty = parse_quantity(word, config_manager)
        if qty is not None:
            item_words = _clean_item_words(words[:i] + words[i + 1:])
            return " ".join(item_words) or None, qty
    return " ".join(_clean_item_words(words)) or None, None


def _scrub_item_name(item_name: str) -> str:
    return " ".join(_COMMAND_WORDS_RE.sub("", item_name).split())


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
