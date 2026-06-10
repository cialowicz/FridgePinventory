"""Tests for the JSGF command grammar generator."""

import os

import pytest

from pi_inventory_system import voice_grammar


@pytest.fixture(autouse=True)
def reset_grammar_cache():
    voice_grammar._reset_cache()
    yield
    voice_grammar._reset_cache()


def test_grammar_header_name_and_public_rule_match():
    jsgf = voice_grammar.build_jsgf()
    assert jsgf.startswith("#JSGF V1.0;")
    # speech_recognition resolves the public rule as "<name>.<name>" from the
    # file basename, so grammar name and public rule name must both match it.
    assert f"grammar {voice_grammar.GRAMMAR_NAME};" in jsgf
    assert f"public <{voice_grammar.GRAMMAR_NAME}>" in jsgf


def test_grammar_includes_command_vocabulary():
    jsgf = voice_grammar.build_jsgf()
    for phrase in ("add", "remove", "undo", "set",
                   "chicken breast", "salmon", "ground beef",
                   "one", "dozen", "a dozen"):
        assert phrase in jsgf


def test_grammar_includes_clear_branch():
    jsgf = voice_grammar.build_jsgf()
    assert "<clear_verb> = clear;" in jsgf
    assert "<clear_verb> [the] <item>" in jsgf


def test_clear_branch_dropped_when_word_unknown():
    known = {"add", "remove", "beef", "ground", "one", "of", "the", "all"}
    jsgf = voice_grammar.build_jsgf(known_words=known)
    assert "<clear_verb>" not in jsgf


def test_unknown_words_are_filtered():
    known = {"add", "remove", "set", "undo", "chicken", "beef", "ground",
             "one", "two", "a", "an", "dozen", "of", "the", "all", "to"}
    jsgf = voice_grammar.build_jsgf(known_words=known)
    assert "tilapia" not in jsgf
    assert "ground beef" in jsgf


def test_phrase_dropped_when_any_word_unknown():
    known = {"add", "remove", "set", "undo", "ice", "beef", "ground",
             "one", "a", "of", "the", "all", "to"}
    jsgf = voice_grammar.build_jsgf(known_words=known)
    # "ice cream" must drop entirely when "cream" is unknown — a grammar
    # containing a dictionary-less word breaks the whole FSG build.
    assert "ice cream" not in jsgf
    assert "ice" not in jsgf.split()
    assert "beef" in jsgf


def test_hyphenated_phrases_are_normalized():
    jsgf = voice_grammar.build_jsgf()
    # 't-bone' / 'ice-cream' must not leak hyphens into grammar tokens
    assert "-" not in jsgf.replace("#JSGF V1.0;", "")


def test_build_fails_when_no_items_survive():
    with pytest.raises(ValueError):
        voice_grammar.build_jsgf(known_words={"add", "remove", "one"})


def test_grammar_file_written_and_stale_fsg_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(voice_grammar, "_grammar_dir", lambda: str(tmp_path))
    monkeypatch.setattr(voice_grammar, "_sphinx_known_words", lambda: None)

    stale_fsg = tmp_path / f"{voice_grammar.GRAMMAR_NAME}.fsg"
    stale_fsg.write_text("stale compiled grammar")

    path = voice_grammar.get_grammar_path()
    assert path is not None
    assert os.path.isfile(path)
    assert path.endswith(f"{voice_grammar.GRAMMAR_NAME}.jsgf")
    with open(path) as f:
        assert f.read().startswith("#JSGF V1.0;")
    # speech_recognition only compiles the .fsg when absent; a stale one
    # would silently keep serving the old vocabulary.
    assert not stale_fsg.exists()

    # Second call is served from cache (same path, file still there)
    assert voice_grammar.get_grammar_path() == path


def test_get_grammar_path_returns_none_and_latches_on_failure(monkeypatch):
    calls = []

    def boom(known_words=None):
        calls.append(1)
        raise ValueError("empty vocabulary")

    monkeypatch.setattr(voice_grammar, "build_jsgf", boom)
    monkeypatch.setattr(voice_grammar, "_sphinx_known_words", lambda: None)
    assert voice_grammar.get_grammar_path() is None
    assert voice_grammar.get_grammar_path() is None
    assert len(calls) == 1  # failure latches; no rebuild attempt per command
