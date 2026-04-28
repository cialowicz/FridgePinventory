"""Tests for ConfigManager — env-var override and defaults path."""

from pi_inventory_system.config_manager import create_config_manager


def test_env_override_int(monkeypatch, tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("display:\n  layout:\n    items_per_row: 4\n")
    monkeypatch.setenv("FRIDGE_DISPLAY__LAYOUT__ITEMS_PER_ROW", "7")
    cm = create_config_manager(str(config_file))
    assert cm.get("display", "layout", "items_per_row") == 7


def test_env_override_float(monkeypatch, tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("commands:\n  similarity_threshold: 0.8\n")
    monkeypatch.setenv("FRIDGE_COMMANDS__SIMILARITY_THRESHOLD", "0.95")
    cm = create_config_manager(str(config_file))
    assert cm.get("commands", "similarity_threshold") == 0.95


def test_env_override_bool(monkeypatch, tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("nlp:\n  enable_spacy: true\n")
    monkeypatch.setenv("FRIDGE_NLP__ENABLE_SPACY", "false")
    cm = create_config_manager(str(config_file))
    assert cm.get("nlp", "enable_spacy") is False


def test_missing_config_falls_back_to_defaults(tmp_path):
    cm = create_config_manager(str(tmp_path / "does-not-exist.yaml"))
    assert cm.get("system", "log_level") == "INFO"


def test_get_with_default():
    cm = create_config_manager("/nonexistent")
    assert cm.get("nope", "no", default="x") == "x"
