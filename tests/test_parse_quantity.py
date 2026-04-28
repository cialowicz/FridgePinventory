"""Direct boundary tests for command_processor.parse_quantity."""

import pytest
from unittest.mock import MagicMock

from pi_inventory_system.command_processor import parse_quantity


@pytest.fixture
def cfg():
    cm = MagicMock()
    cm.get_command_config.return_value = {}
    return cm


@pytest.mark.parametrize("text, expected", [
    ("3", 3),
    ("0", 0),
    ("10000", 10000),
    ("one", 1),
    ("dozen", 12),
])
def test_valid_quantities(cfg, text, expected):
    assert parse_quantity(text, cfg) == expected


@pytest.mark.parametrize("text", ["-1", "10001", "", "   ", "banana", None])
def test_rejected_quantities(cfg, text):
    assert parse_quantity(text, cfg) is None


def test_special_quantities_from_config(cfg):
    cfg.get_command_config.return_value = {'special_quantities': {'few': 3}}
    assert parse_quantity("few", cfg) == 3


def test_word2number_chain(cfg):
    cm = MagicMock()
    cm.get_command_config.return_value = {}
    assert parse_quantity("twenty", cm) == 20
