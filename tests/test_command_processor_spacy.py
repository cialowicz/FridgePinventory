# Tests for the spaCy integration in the command processor
import pytest
from unittest.mock import MagicMock, patch

import pi_inventory_system.command_processor
from pi_inventory_system.command_processor import interpret_command
from pi_inventory_system.inventory_item import InventoryItem


@pytest.fixture(autouse=True)
def reset_nlp_globals():
    """Reset the global _nlp and _nlp_load_attempted flags before each test."""
    pi_inventory_system.command_processor._nlp = None
    pi_inventory_system.command_processor._nlp_load_attempted = False
    yield

@pytest.fixture
def spacy_config_manager():
    """Mock the config manager to enable spaCy."""
    config_manager = MagicMock()
    config_manager.get_command_config.return_value = {}
    config_manager.get_nlp_config.return_value = {"enable_spacy": True}
    return config_manager


def create_mock_doc(tokens):
    """
    Factory function to create a mock spaCy Doc object from a list of token dicts.
    Each token dict should have 'text' and 'lemma_'.
    """
    mock_tokens = []
    for token_data in tokens:
        mock_token = MagicMock()
        mock_token.text = token_data["text"]
        mock_token.lemma_ = token_data["lemma_"]
        # Set a default, as the code checks this attribute
        mock_token.pos_ = token_data.get("pos_", "VERB")
        mock_tokens.append(mock_token)

    # The 'doc' object is iterable
    mock_doc = MagicMock()
    mock_doc.__iter__.return_value = iter(mock_tokens)
    mock_doc.text = " ".join(t.text for t in mock_tokens)
    return mock_doc


@patch("pi_inventory_system.command_processor.spacy.load")
def test_verb_classification_with_spacy(mock_spacy_load, spacy_config_manager):
    """
    Test that a verb like 'bought' is correctly classified as an 'add'
    command when spaCy is enabled and provides the lemma 'buy'.
    """
    # Arrange:
    # 1. Mock the return value of spacy.load to be a mock nlp object
    mock_nlp = MagicMock()
    mock_spacy_load.return_value = mock_nlp

    # 2. When the nlp object is called with our command, return a mock Doc
    #    that simulates the result of spaCy's analysis.
    mock_doc = create_mock_doc(
        [
            {"text": "I", "lemma_": "I"},
            {"text": "bought", "lemma_": "buy"},
            {"text": "three", "lemma_": "three"},
            {"text": "apples", "lemma_": "apple"},
        ]
    )
    mock_nlp.return_value = mock_doc

    # Act:
    # Interpret the command with spaCy enabled
    command_type, item = interpret_command("I bought three apples", spacy_config_manager)

    # Assert:
    # The verb 'bought' (lemma 'buy') should be classified as 'add'
    assert command_type == "add"
    assert item == InventoryItem(item_name="apples", quantity=3)
    # Ensure spaCy was actually loaded
    mock_spacy_load.assert_called_once()


@patch("pi_inventory_system.command_processor.spacy.load")
def test_multi_word_quantity_with_spacy(mock_spacy_load, spacy_config_manager):
    """
    Test that multi-word quantities are correctly parsed when spaCy is enabled.
    For example, "add twenty-five bananas".
    """
    mock_nlp = MagicMock()
    mock_spacy_load.return_value = mock_nlp
    mock_doc = create_mock_doc(
        [
            {"text": "add", "lemma_": "add"},
            {"text": "twenty", "lemma_": "twenty"},
            {"text": "five", "lemma_": "five"},
            {"text": "bananas", "lemma_": "banana"},
        ]
    )
    mock_nlp.return_value = mock_doc

    command_type, item = interpret_command("add twenty-five bananas", spacy_config_manager)

    assert command_type == "add"
    assert item == InventoryItem(item_name="bananas", quantity=25)
    mock_spacy_load.assert_called_once()


@patch("pi_inventory_system.command_processor.spacy.load")
def test_item_name_starting_with_number(mock_spacy_load, spacy_config_manager):
    """
    Test that item names starting with numbers are correctly handled,
    e.g., "add 3 of 24-pack coke"
    """
    mock_nlp = MagicMock()
    mock_spacy_load.return_value = mock_nlp
    mock_doc = create_mock_doc(
        [
            {"text": "add", "lemma_": "add"},
            {"text": "3", "lemma_": "3"},
            {"text": "of", "lemma_": "of"},
            {"text": "24-pack", "lemma_": "24-pack"},
            {"text": "coke", "lemma_": "coke"},
        ]
    )
    mock_nlp.return_value = mock_doc

    command_type, item = interpret_command("add 3 of 24-pack coke", spacy_config_manager)

    assert command_type == "add"
    assert item == InventoryItem(item_name="24-pack coke", quantity=3)
    mock_spacy_load.assert_called_once()


@patch("pi_inventory_system.command_processor.spacy.load")
def test_unrecognized_command_with_spacy(mock_spacy_load, spacy_config_manager):
    """Unrecognized commands return (None, None) when spaCy is enabled."""
    mock_nlp = MagicMock()
    mock_spacy_load.return_value = mock_nlp
    mock_doc = create_mock_doc(
        [
            {"text": "Fly", "lemma_": "fly"},
            {"text": "to", "lemma_": "to"},
            {"text": "the", "lemma_": "the"},
            {"text": "moon", "lemma_": "moon"},
        ]
    )
    mock_nlp.return_value = mock_doc

    command_type, item = interpret_command("Fly to the moon", spacy_config_manager)

    assert command_type is None
    assert item is None
    mock_spacy_load.assert_called_once()
