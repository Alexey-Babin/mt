"""Tests for languages.py"""

import json
from unittest.mock import mock_open, patch

import pytest

from mt_server.languages import (
    LANGUAGES_DB_FILE,
    LanguageRecord,
    languages_db,
    read_languages_db,
)


class TestReadLanguagesDb:
    """Tests for read_languages_db function."""

    def test_read_languages_db_success(self):
        """Test successful reading of languages database."""
        sample_data = {
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

        with patch("builtins.open", mock_open(read_data=json.dumps(sample_data))):
            result = read_languages_db()

            assert isinstance(result, dict)
            assert len(result) == 2
            assert "eng_Latn" in result
            assert "rus_Cyrl" in result
            assert result["eng_Latn"]["en"] == "English"
            assert result["eng_Latn"]["iso2"] == "en"

    def test_read_languages_db_empty_file(self):
        """Test reading empty languages database."""
        with patch("builtins.open", mock_open(read_data="{}")):
            result = read_languages_db()

            assert isinstance(result, dict)
            assert len(result) == 0

    def test_read_languages_db_invalid_json(self):
        """Test reading invalid JSON raises error."""
        with patch("builtins.open", mock_open(read_data="invalid json")):
            with pytest.raises(json.JSONDecodeError):
                read_languages_db()

    def test_read_languages_db_file_path(self):
        """Test that function reads from correct file."""
        sample_data = {
            "eng_Latn": {
                "en": "English",
                "ru": "Английский",
                "native": "English",
                "iso": "eng",
                "iso2": "en",
                "ord": 1,
            }
        }

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(sample_data))
        ) as mock_file:
            read_languages_db()
            mock_file.assert_called_once_with(LANGUAGES_DB_FILE, "r")


class TestLanguagesDb:
    """Tests for the global languages_db fixture."""

    def test_languages_db_is_dict(self):
        """Test that languages_db is a dictionary."""
        assert isinstance(languages_db, dict)

    def test_languages_db_has_expected_keys(self):
        """Test that languages_db has expected language keys."""
        # Check for some common language codes
        expected_languages = ["eng_Latn", "rus_Cyrl"]
        for lang in expected_languages:
            if lang in languages_db:
                record = languages_db[lang]
                assert isinstance(record, dict)
                assert "en" in record
                assert "ru" in record
                assert "native" in record
                assert "iso" in record
                assert "iso2" in record
                assert "ord" in record

    def test_language_record_structure(self):
        """Test that language records have correct structure."""
        for lang_code, record in languages_db.items():
            assert isinstance(lang_code, str)
            assert "en" in record
            assert "ru" in record
            assert "native" in record
            assert "iso" in record
            assert "iso2" in record
            assert "ord" in record
            assert isinstance(record["ord"], int)


class TestLanguageRecordTypedDict:
    """Tests for LanguageRecord TypedDict type hints."""

    def test_language_record_has_all_fields(self):
        """Test that LanguageRecord has all required fields."""
        sample_record = {
            "en": "English",
            "ru": "Английский",
            "native": "English",
            "iso": "eng",
            "iso2": "en",
            "ord": 1,
        }

        # This should not raise a type error if the TypedDict is correct
        record: LanguageRecord = sample_record  # type: ignore

        assert record["en"] == "English"
        assert record["ru"] == "Английский"
        assert record["native"] == "English"
        assert record["iso"] == "eng"
        assert record["iso2"] == "en"
        assert record["ord"] == 1
