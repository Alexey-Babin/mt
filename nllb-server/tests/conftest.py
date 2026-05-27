# tests/conftest.py
"""Common fixtures and configuration for tests."""

from unittest.mock import MagicMock

import pytest

from mt_server.engine import Translator
from mt_server.translation_service import TranslationService


@pytest.fixture
def mock_translator():
    """Create a mock translator for testing."""
    mock = MagicMock(spec=Translator)
    mock.model_name = "nllb-200-distilled-600M"
    mock.has_cuda = False
    mock.device = "cpu"
    mock.tokenizer = MagicMock()
    mock.languages = {
        "eng_Latn": {
            "en": "English",
            "ru": "Английский",
            "native": "English",
            "iso": "eng",
            "iso2": "en",
            "ord": 1,
        },
        "rus_Cyrl": {
            "en": "Russian",
            "ru": "Русский",
            "native": "Русский",
            "iso": "rus",
            "iso2": "ru",
            "ord": 2,
        },
    }
    mock.translate = MagicMock(return_value="Translated text")
    mock.get_supported_languages = MagicMock(return_value=["eng_Latn", "rus_Cyrl"])
    return mock


@pytest.fixture
def translation_service(mock_translator):
    """Create a TranslationService instance for tests."""
    return TranslationService(mock_translator)


@pytest.fixture
def mock_tokenizer():
    """Create a mock tokenizer for testing."""
    mock = MagicMock()
    mock.return_value = {"input_ids": [1, 2, 3, 4, 5]}
    return mock


@pytest.fixture
def mock_segmenter():
    """Create a mock segmenter for testing."""
    mock = MagicMock()
    mock.segment = MagicMock(return_value=["Sentence 1.", "Sentence 2."])
    return mock


@pytest.fixture
def sample_text():
    """Sample text for testing."""
    return "Hello world. This is a test. How are you?"


@pytest.fixture
def sample_markdown():
    """Sample markdown text for testing."""
    return (
        "# Header\n\n**Bold text** and *italic text*.\n\n- List item 1\n- List item 2"
    )


@pytest.fixture
def sample_blocks():
    """Sample text with multiple blocks."""
    return "Block 1\n\nBlock 2\n\nBlock 3"
