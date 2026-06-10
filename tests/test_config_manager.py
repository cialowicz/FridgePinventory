"""Tests for ConfigManager — env-var override and defaults path."""

import pytest

from pi_inventory_system.config_manager import create_config_manager
from pi_inventory_system.exceptions import ConfigurationError


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


def test_env_override_wal_mode_remains_string(monkeypatch, tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("database_advanced:\n  wal_mode: WAL\n")
    monkeypatch.setenv("FRIDGE_DATABASE_ADVANCED__WAL_MODE", "DELETE")
    cm = create_config_manager(str(config_file))
    assert cm.get("database_advanced", "wal_mode") == "DELETE"


def test_env_override_fractional_db_timeout(monkeypatch, tmp_path):
    """database_advanced.timeout is a float; '12.5' must not be silently
    dropped by an int-only conversion."""
    config_file = tmp_path / "c.yaml"
    config_file.write_text("database_advanced:\n  timeout: 30.0\n")
    monkeypatch.setenv("FRIDGE_DATABASE_ADVANCED__TIMEOUT", "12.5")
    cm = create_config_manager(str(config_file))
    assert cm.get("database_advanced", "timeout") == 12.5


def test_env_override_whole_number_voice_timeout(monkeypatch, tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("audio:\n  voice_recognition:\n    timeout: 5\n")
    monkeypatch.setenv("FRIDGE_AUDIO__VOICE_RECOGNITION__TIMEOUT", "8")
    cm = create_config_manager(str(config_file))
    assert cm.get("audio", "voice_recognition", "timeout") == 8.0


def test_empty_config_file_loads_defaults(tmp_path):
    config_file = tmp_path / "empty.yaml"
    config_file.write_text("")
    cm = create_config_manager(str(config_file))
    assert cm.get("missing", default="fallback") == "fallback"
    assert cm.get("system", "activation_mode") == "auto"


def test_partial_config_merges_with_defaults(tmp_path):
    config_file = tmp_path / "partial.yaml"
    config_file.write_text("display:\n  layout:\n    items_per_row: 3\n")
    cm = create_config_manager(str(config_file))
    assert cm.get("display", "layout", "items_per_row") == 3
    assert cm.get("display", "layout", "lozenge_height") == 60


def test_invalid_yaml_raises_configuration_error(tmp_path):
    config_file = tmp_path / "bad.yaml"
    config_file.write_text("system: [")
    with pytest.raises(ConfigurationError):
        create_config_manager(str(config_file))


def test_invalid_activation_mode_raises(tmp_path):
    config_file = tmp_path / "bad-mode.yaml"
    config_file.write_text("system:\n  activation_mode: teleport\n")
    with pytest.raises(ConfigurationError):
        create_config_manager(str(config_file))


def test_missing_config_falls_back_to_defaults(tmp_path):
    cm = create_config_manager(str(tmp_path / "does-not-exist.yaml"))
    assert cm.get("system", "log_level") == "INFO"


def test_get_with_default():
    cm = create_config_manager("/nonexistent")
    assert cm.get("nope", "no", default="x") == "x"
