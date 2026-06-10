"""Voice-command interpretation: text -> (command_type, InventoryItem)."""

import logging
import re
import threading
from typing import Optional, Tuple

from .constants import MAX_COMMAND_LEN, MAX_QUANTITY
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
_nlp_load_failures = 0
_NLP_MAX_LOAD_FAILURES = 3
_nlp_lock = threading.Lock()

UNDO_WORDS = ('undo', 'reverse', 'take back', 'cancel', 'revert')
# Word-boundary match so e.g. "cancelled" or "reversed" inside an item
# phrase does not classify the whole command as undo.
_UNDO_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(word) for word in UNDO_WORDS) + r")\b"
)
ADD_VERBS = ('add', 'put', 'place', 'store', 'stock', 'insert', 'got', 'bought', 'purchased')
REMOVE_VERBS = ('remove', 'take', 'delete', 'use', 'used', 'consume', 'consumed',
                'subtract', 'ate', 'finished')
SET_VERBS = ('set', 'change', 'update', 'adjust', 'modify', 'correct', 'fix')
# "clear X" is an alias for "remove all X"; rewritten before classification.
CLEAR_VERBS = ('clear',)
VERB_LABELS = ((ADD_VERBS, "add"), (REMOVE_VERBS, "remove"), (SET_VERBS, "set"))
ITEM_FILLER_WORDS = {'of', 'the'}

_CLEAR_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(verb) for verb in CLEAR_VERBS) + r")\b"
)


def _alias_clear_command(command_text: str) -> str:
    """Rewrite 'clear X' to 'remove all X'.

    Only when no other command verb precedes the clear-verb, so item phrases
    like 'add clear soup' and undo phrasings keep their meaning."""
    match = _CLEAR_RE.search(command_text)
    if not match:
        return command_text
    prefix = command_text[:match.start()]
    earlier_verbs = tuple(
        verb for verbs, _ in VERB_LABELS for verb in verbs) + UNDO_WORDS
    earlier_pattern = "|".join(re.escape(verb) for verb in earlier_verbs)
    if re.search(rf"\b(?:{earlier_pattern})\b", prefix):
        return command_text
    return "remove all " + command_text[match.end():].lstrip()

DEFAULT_QUANTITIES = {
    'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3,
    'four': 4, 'five': 5, 'six': 6, 'seven': 7,
    'eight': 8, 'nine': 9, 'ten': 10, 'dozen': 12,
}

_QTY_PARSED = "parsed"
_QTY_MISSING = "missing"
_QTY_INVALID = "invalid"
_NUMERIC_TOKEN_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


def _ensure_nlp(config_manager):
    """Load spaCy lazily. Permanent skips (no spacy installed, disabled in
    config) latch via _nlp_load_attempted. OSError can be transient (partially
    written model) but is also what spaCy raises when the model simply is not
    installed, so retries are capped: after _NLP_MAX_LOAD_FAILURES failures we
    latch onto rule-based parsing instead of paying a model-load attempt on
    every command."""
    global _nlp, _nlp_load_attempted, _nlp_load_failures
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
            _nlp_load_failures = 0
        except OSError as e:
            _nlp = None
            _nlp_load_failures += 1
            if _nlp_load_failures >= _NLP_MAX_LOAD_FAILURES:
                _nlp_load_attempted = True
                logging.warning(
                    f"spaCy model '{model_name}' failed to load "
                    f"{_nlp_load_failures} times ({e}); "
                    "using rule-based parsing for the rest of this process")
            else:
                logging.warning(
                    f"spaCy model '{model_name}' load failed "
                    f"(attempt {_nlp_load_failures}/{_NLP_MAX_LOAD_FAILURES}): {e}; "
                    "will retry on next command")
        except Exception as e:
            logging.warning(f"spaCy model '{model_name}' unavailable, falling back: {e}")
            _nlp = None
            _nlp_load_attempted = True
        return _nlp


def _special_quantities(config_manager) -> dict:
    """Merge configured quantity aliases with built-in command vocabulary."""
    configured = {}
    if config_manager is not None:
        configured = config_manager.get_command_config().get('special_quantities') or {}
    return {**DEFAULT_QUANTITIES, **configured}


def _parse_quantity_internal(text: str, config_manager) -> tuple[str, Optional[int]]:
    """Parse a quantity and distinguish absent words from invalid quantities."""
    if not text:
        return _QTY_MISSING, None
    text = text.strip()

    try:
        quantity = int(text)
    except (ValueError, OverflowError):
        quantity = None

    if quantity is None:
        text_lower = text.lower()
        special = _special_quantities(config_manager)
        if text_lower in special:
            quantity = special[text_lower]
        elif W2N_AVAILABLE:
            try:
                quantity = w2n.word_to_num(text_lower)
            except (ValueError, AttributeError):
                quantity = None

    if quantity is None:
        if _NUMERIC_TOKEN_RE.match(text):
            return _QTY_INVALID, None
        return _QTY_MISSING, None
    if quantity < 0 or quantity > MAX_QUANTITY:
        logging.warning(f"Quantity out of range: {quantity}")
        return _QTY_INVALID, None
    return _QTY_PARSED, quantity


def parse_quantity(text: str, config_manager) -> Optional[int]:
    """Parse a quantity from text, accepting digits and number-words.
    Returns None for invalid, negative, out-of-range, or absent values."""
    status, quantity = _parse_quantity_internal(text, config_manager)
    return quantity if status == _QTY_PARSED else None


def _classify_verb(command_text: str, config_manager) -> Optional[str]:
    """Decide whether the user said add / remove / set / undo / nothing.
    Tries spaCy lemmas first, falls back to keyword regex."""
    if _UNDO_RE.search(command_text):
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

    matches = []
    for verb_set, label in VERB_LABELS:
        verb_pattern = "|".join(
            re.escape(verb) for verb in sorted(verb_set, key=len, reverse=True)
        )
        match = re.search(rf"\b(?:{verb_pattern})\b", command_text)
        if match:
            matches.append((match.start(), label))
    if matches:
        return min(matches, key=lambda item: item[0])[1]
    return None


def _strip_command_verb(command_text: str, verbs) -> str:
    """Remove the matched command verb while preserving the item phrase."""
    verb_pattern = "|".join(
        re.escape(verb) for verb in sorted(verbs, key=len, reverse=True)
    )
    return re.sub(
        rf"^.*?\b(?:{verb_pattern})\b\s*",
        "",
        command_text,
        count=1,
    ).strip()


def _clean_item_words(words):
    return [word for word in words if word not in ITEM_FILLER_WORDS]


def _parse_quantity_words(words, config_manager):
    """Return (quantity, consumed_words) for a leading quantity phrase."""
    if not words:
        return None, 0, False

    first_status, first = _parse_quantity_internal(words[0], config_manager)
    if first_status == _QTY_INVALID:
        return None, 0, True
    if len(words) > 1 and words[1] == "dozen":
        if words[0] in ("a", "an", "one"):
            return 12, 2, False
        if first is not None:
            quantity = first * 12
            if quantity > MAX_QUANTITY:
                logging.warning(f"Quantity out of range: {quantity}")
                return None, 0, True
            return quantity, 2, False

    if first is not None:
        return first, 1, False

    if len(words) > 1 and words[0] in ("a", "an"):
        second_status, second = _parse_quantity_internal(words[1], config_manager)
        if second_status == _QTY_INVALID:
            return None, 0, True
        if second is not None:
            return second, 2, False

    for end in range(min(4, len(words)), 1, -1):
        status, quantity = _parse_quantity_internal(" ".join(words[:end]), config_manager)
        if status == _QTY_PARSED:
            return quantity, end, False
        if status == _QTY_INVALID:
            return None, 0, True

    return None, 0, False


def _extract_set_arguments(command_text: str, config_manager):
    """Parse 'set X to Y' or 'set X Y'. Returns (item_name, quantity) or (None, None)."""
    text = _strip_command_verb(command_text, SET_VERBS)
    if not text or re.match(r"^to(?:\s|$)", text):
        return None, None
    match = re.search(r"(.+?)\s+to\s+(.+?)\s*$", text)
    if match:
        status, quantity = _parse_quantity_internal(match.group(2), config_manager)
        return match.group(1).strip(), quantity if status == _QTY_PARSED else None
    match = re.search(r"(.+?)\s+(\S+)\s*$", text)
    if match:
        status, quantity = _parse_quantity_internal(match.group(2), config_manager)
        return match.group(1).strip(), quantity if status == _QTY_PARSED else None
    return None, None


def _extract_add_remove_arguments(command_text: str, command_type: str, config_manager):
    """Strip the command verb and pull the first quantity-token + item name."""
    verbs = ADD_VERBS if command_type == "add" else REMOVE_VERBS
    text = _strip_command_verb(command_text, verbs)
    words = text.split()
    if not words:
        return None, None

    if command_type == "remove" and words[0] == "all":
        item_words = _clean_item_words(words[1:])
        return " ".join(item_words) or None, MAX_QUANTITY

    quantity, consumed, invalid_quantity = _parse_quantity_words(words, config_manager)
    if invalid_quantity:
        return None, None
    if quantity is not None:
        item_words = _clean_item_words(words[consumed:])
        return " ".join(item_words) or None, quantity

    for i, word in enumerate(words):
        status, qty = _parse_quantity_internal(word, config_manager)
        if status == _QTY_INVALID:
            return None, None
        if status == _QTY_PARSED:
            item_words = _clean_item_words(words[:i] + words[i + 1:])
            return " ".join(item_words) or None, qty
    return " ".join(_clean_item_words(words)) or None, None


def _scrub_item_name(item_name: str) -> str:
    return " ".join(item_name.split())


def interpret_command(
    command_text: str,
    config_manager,
) -> Tuple[Optional[str], Optional[InventoryItem]]:
    """Interpret a voice command. Returns (command_type, InventoryItem) or (None, None)."""
    if not command_text or not isinstance(command_text, str):
        return None, None
    if len(command_text) > MAX_COMMAND_LEN:
        logging.warning(f"Command too long: {len(command_text)} characters")
        return None, None

    command_text = _alias_clear_command(command_text.lower().strip())
    command_type = _classify_verb(command_text, config_manager)
    if command_type is None:
        return None, None
    if command_type == "undo":
        logging.info(f"Undo command detected: {command_text}")
        return "undo", None

    if command_type == "set":
        item_name, quantity = _extract_set_arguments(command_text, config_manager)
    else:
        item_name, quantity = _extract_add_remove_arguments(
            command_text,
            command_type,
            config_manager,
        )

    if item_name:
        item_name = _scrub_item_name(item_name)
    if quantity is None and command_type == "set":
        logging.warning(f"Could not extract set quantity from: {command_text}")
        return command_type, None
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
