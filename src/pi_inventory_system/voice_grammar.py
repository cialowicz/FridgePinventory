"""Generate a JSGF command grammar so PocketSphinx only decodes valid commands.

PocketSphinx with the open English language model routinely mangles short
command phrases ("add chicken" -> "at a chicken"). Constraining decoding to
a grammar built from the exact vocabulary the command processor accepts
removes that failure class: the decoder can only emit strings the parser
understands. Vocabulary is sourced from command_processor and item_normalizer
so the grammar cannot drift from what interpret_command() actually parses.
"""

import logging
import os
import re
import tempfile
import threading

from .command_processor import (
    ADD_VERBS,
    DEFAULT_QUANTITIES,
    REMOVE_VERBS,
    SET_VERBS,
    UNDO_WORDS,
)
from .item_normalizer import ITEM_SYNONYMS

logger = logging.getLogger(__name__)

# speech_recognition compiles "<name>.jsgf" by resolving the public rule
# "<name>.<name>" from the file basename, so the grammar name, public rule
# name, and file basename must all be identical.
GRAMMAR_NAME = "fridge_commands"

# Number words beyond DEFAULT_QUANTITIES that parse_quantity handles via
# word2number.
_EXTRA_QUANTITY_WORDS = (
    'a dozen', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen',
    'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty',
)

_PHRASE_RE = re.compile(r"^[a-z ]+$")

_lock = threading.Lock()
_cached_path = None
_build_failed = False


def _normalize_phrase(phrase: str):
    """Lowercase, fold hyphens to spaces, reject anything non-alphabetic."""
    phrase = phrase.lower().replace('-', ' ')
    phrase = ' '.join(phrase.split())
    return phrase if phrase and _PHRASE_RE.match(phrase) else None


def _keep_known(phrases, known_words):
    """Normalize phrases and drop any containing a word the Sphinx dictionary
    does not know — one out-of-vocabulary word breaks the whole FSG build."""
    kept, dropped = [], []
    for phrase in phrases:
        normalized = _normalize_phrase(phrase)
        if normalized is None or (
            known_words is not None
            and any(word not in known_words for word in normalized.split())
        ):
            dropped.append(phrase)
        else:
            kept.append(normalized)
    return sorted(set(kept)), dropped


def build_jsgf(known_words=None) -> str:
    """Build the JSGF grammar text.

    Raises ValueError if filtering leaves no usable verbs or items.
    """
    all_dropped = []

    def keep(phrases):
        kept, dropped = _keep_known(phrases, known_words)
        all_dropped.extend(dropped)
        return kept

    action_verbs = keep(ADD_VERBS + REMOVE_VERBS)
    set_verbs = keep(SET_VERBS)
    undo_words = keep(UNDO_WORDS)
    quantities = keep(tuple(DEFAULT_QUANTITIES) + _EXTRA_QUANTITY_WORDS)
    items = keep(
        tuple(ITEM_SYNONYMS)
        + tuple(s for synonyms in ITEM_SYNONYMS.values() for s in synonyms)
    )

    if all_dropped:
        logger.info(
            "Grammar dropped phrases not usable with the Sphinx dictionary: "
            f"{sorted(set(all_dropped))}"
        )
    if not action_verbs or not items:
        raise ValueError("Command grammar vocabulary is empty after filtering")

    def alts(phrases):
        return ' | '.join(phrases)

    rules = [
        f"<verb> = {alts(action_verbs)};",
        f"<item> = {alts(items)};",
    ]
    branches = [
        "<verb> [<quantity>] [of] [the] <item>",
        "<verb> all [the] <item>",
    ]
    if quantities:
        rules.append(f"<quantity> = {alts(quantities)};")
    else:
        branches[0] = "<verb> [of] [the] <item>"
    if undo_words:
        rules.append(f"<undo> = {alts(undo_words)};")
        branches.insert(0, "<undo>")
    if set_verbs and quantities:
        rules.append(f"<set_verb> = {alts(set_verbs)};")
        branches.append("<set_verb> [the] <item> to <quantity>")

    public_rule = (
        f"public <{GRAMMAR_NAME}> =\n      "
        + "\n    | ".join(branches)
        + ";"
    )
    return (
        "#JSGF V1.0;\n"
        f"grammar {GRAMMAR_NAME};\n\n"
        + "\n".join(rules)
        + "\n\n"
        + public_rule
        + "\n"
    )


def _sphinx_known_words():
    """Load the word list from speech_recognition's bundled Sphinx dictionary.

    Returns None (no filtering) when the dictionary cannot be found, e.g. on
    dev machines without pocketsphinx data installed.
    """
    try:
        import speech_recognition as sr_module
    except ImportError:
        return None
    dict_path = os.path.join(
        os.path.dirname(os.path.abspath(sr_module.__file__)),
        'pocketsphinx-data', 'en-US', 'pronounciation-dictionary.dict',
    )
    if not os.path.isfile(dict_path):
        logger.debug(f"Sphinx dictionary not found at {dict_path}")
        return None
    words = set()
    with open(dict_path, encoding='utf-8', errors='replace') as f:
        for line in f:
            token = line.split(None, 1)[0] if line.strip() else ''
            if token:
                # Alternate pronunciations appear as "word(2)"
                words.add(token.split('(')[0].lower())
    return words or None


def _grammar_dir() -> str:
    return tempfile.gettempdir()


def get_grammar_path():
    """Return the path of the generated .jsgf file, or None if unavailable.

    Builds and caches on first call; a build failure latches so the cost is
    not re-paid on every voice command.
    """
    global _cached_path, _build_failed
    with _lock:
        if _cached_path and os.path.isfile(_cached_path):
            return _cached_path
        if _build_failed:
            return None
        try:
            jsgf = build_jsgf(known_words=_sphinx_known_words())
            path = os.path.join(_grammar_dir(), GRAMMAR_NAME + '.jsgf')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(jsgf)
            # speech_recognition compiles the .jsgf to a .fsg next to it and
            # reuses the .fsg while it exists; a stale one would keep serving
            # the old vocabulary after this grammar changes.
            fsg_path = os.path.join(_grammar_dir(), GRAMMAR_NAME + '.fsg')
            if os.path.exists(fsg_path):
                os.remove(fsg_path)
            _cached_path = path
            logger.info(f"Sphinx command grammar written to {path}")
            return path
        except Exception as e:
            _build_failed = True
            logger.warning(
                f"Could not build Sphinx command grammar: {e}; "
                "recognition will use the open language model"
            )
            return None


def _reset_cache():
    """Test hook: clear the cached grammar path and failure latch."""
    global _cached_path, _build_failed
    with _lock:
        _cached_path = None
        _build_failed = False
