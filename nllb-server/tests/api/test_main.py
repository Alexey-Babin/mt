"""Tests for FastAPI endpoints in main.py"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from mt_server.engine import TranslationEngineProtocol
from mt_server.main import app, get_translation_service, get_translator_engine
from mt_server.translation_service import TextFormat, TranslationService


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def _make_to_thread_mock():
    """Create a mock asyncio.to_thread that returns an awaitable."""

    async def async_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    return async_to_thread


class TestTranslateEndpoint:
    """Tests for /translate endpoint."""

    def test_translate_endpoint_success(self, client):
        """Test successful translation request."""
        mock_engine = MagicMock()
        mock_engine.validate_language = MagicMock()
        mock_service = MagicMock(spec=TranslationService)
        mock_service.translate = MagicMock(return_value="Translated text")
        mock_service.engine = mock_engine

        def override_get_translation_service():
            return mock_service

        app.dependency_overrides[get_translation_service] = (
            override_get_translation_service
        )

        try:
            with patch(
                "mt_server.main.asyncio.to_thread",
                side_effect=_make_to_thread_mock(),
            ):
                response = client.post(
                    "/translate",
                    json={
                        "text": "Hello world",
                        "src_lang": "eng_Latn",
                        "target_lang": "rus_Cyrl",
                        "format": "plain",
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["translated_text"] == "Translated text"
            assert data["source_lang"] == "eng_Latn"
            assert data["target_lang"] == "rus_Cyrl"
        finally:
            app.dependency_overrides.clear()

    def test_translate_endpoint_empty_text(self, client):
        """Test translation with empty text returns 400."""
        mock_engine = MagicMock()
        mock_engine.validate_language = MagicMock()
        mock_service = MagicMock(spec=TranslationService)
        mock_service.translate = MagicMock(return_value="Translated text")
        mock_service.engine = mock_engine

        def override_get_translation_service():
            return mock_service

        app.dependency_overrides[get_translation_service] = (
            override_get_translation_service
        )

        try:
            response = client.post(
                "/translate",
                json={
                    "text": "",
                    "src_lang": "eng_Latn",
                    "target_lang": "rus_Cyrl",
                },
            )

            assert response.status_code == 400
            assert response.json()["detail"] == "Text cannot be empty"
        finally:
            app.dependency_overrides.clear()

    def test_translate_endpoint_service_not_ready(self, client):
        """Test translation when service is not initialized."""

        def override_get_translation_service():
            raise HTTPException(
                status_code=503, detail="Translation service not initialized"
            )

        def override_get_translator_engine():
            raise HTTPException(
                status_code=503, detail="Translation engine not initialized"
            )

        app.dependency_overrides[get_translation_service] = (
            override_get_translation_service
        )
        app.dependency_overrides[get_translator_engine] = override_get_translator_engine

        try:
            response = client.post(
                "/translate",
                json={
                    "text": "Hello",
                    "src_lang": "eng_Latn",
                    "target_lang": "rus_Cyrl",
                },
            )

            assert response.status_code == 503
            assert response.json()["detail"] == "Translation service not initialized"
        finally:
            app.dependency_overrides.clear()

    def test_translate_endpoint_internal_error(self, client):
        """Test translation with internal error."""
        mock_engine = MagicMock()
        mock_engine.validate_language = MagicMock()
        mock_service = MagicMock(spec=TranslationService)
        mock_service.translate = MagicMock(side_effect=Exception("Translation failed"))
        mock_service.engine = mock_engine

        def override_get_translation_service():
            return mock_service

        app.dependency_overrides[get_translation_service] = (
            override_get_translation_service
        )

        try:
            with patch(
                "mt_server.main.asyncio.to_thread",
                side_effect=_make_to_thread_mock(),
            ):
                response = client.post(
                    "/translate",
                    json={
                        "text": "Hello",
                        "src_lang": "eng_Latn",
                        "target_lang": "rus_Cyrl",
                    },
                )

            assert response.status_code == 500
            assert response.json()["detail"] == "Internal translation error"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.parametrize("format_value", ["auto", "plain", "markdown"])
    def test_translate_endpoint_with_different_formats(self, client, format_value):
        """Test translation with different format values."""
        mock_engine = MagicMock()
        mock_engine.validate_language = MagicMock()
        mock_service = MagicMock(spec=TranslationService)
        mock_service.translate = MagicMock(return_value="Translated text")
        mock_service.engine = mock_engine

        def override_get_translation_service():
            return mock_service

        app.dependency_overrides[get_translation_service] = (
            override_get_translation_service
        )

        try:
            with patch(
                "mt_server.main.asyncio.to_thread",
                side_effect=_make_to_thread_mock(),
            ):
                response = client.post(
                    "/translate",
                    json={
                        "text": "Hello",
                        "src_lang": "eng_Latn",
                        "target_lang": "rus_Cyrl",
                        "format": format_value,
                    },
                )

            assert response.status_code == 200
            # Verify format was passed correctly
            call_kwargs = mock_service.translate.call_args[1]
            assert call_kwargs["format"] == TextFormat(format_value)
        finally:
            app.dependency_overrides.clear()


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_endpoint_ready(self, client):
        """Test health check when service is ready."""
        mock_engine = MagicMock(spec=TranslationEngineProtocol)
        mock_engine.model_name = "nllb-200-distilled-600M"
        mock_engine.has_cuda = True
        mock_engine.device = "cuda"

        mock_service = MagicMock(spec=TranslationService)

        def override_get_translator_engine():
            return mock_engine

        def override_get_translation_service():
            return mock_service

        app.dependency_overrides[get_translator_engine] = override_get_translator_engine
        app.dependency_overrides[get_translation_service] = (
            override_get_translation_service
        )

        try:
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert data["model"] == "nllb-200-distilled-600M"
            assert data["gpu"] is True
            assert data["device"] == "cuda"
        finally:
            app.dependency_overrides.clear()

    def test_health_endpoint_loading(self, client):
        """Test health check when service is loading."""

        def override_get_translator_engine():
            raise HTTPException(
                status_code=503, detail="Translation engine not initialized"
            )

        def override_get_translation_service():
            raise HTTPException(
                status_code=503, detail="Translation service not initialized"
            )

        app.dependency_overrides[get_translator_engine] = override_get_translator_engine
        app.dependency_overrides[get_translation_service] = (
            override_get_translation_service
        )

        try:
            response = client.get("/health")

            assert response.status_code == 503
        finally:
            app.dependency_overrides.clear()


class TestLanguagesEndpoint:
    """Tests for /languages endpoint."""

    def test_languages_endpoint_members_only(self, client):
        """Test languages endpoint with members_only level."""
        mock_engine = MagicMock(spec=TranslationEngineProtocol)
        mock_engine.languages = {
            "eng_Latn": {"en": "English", "ord": 1},
            "rus_Cyrl": {"en": "Russian", "ord": 2},
            "fra_Latn": {"en": "French", "ord": 10},
        }

        def override_get_translator_engine():
            return mock_engine

        app.dependency_overrides[get_translator_engine] = override_get_translator_engine

        try:
            response = client.get("/languages?language_level=members_only")

            assert response.status_code == 200
            data = response.json()
            # Should only include languages with ord < 10
            assert "eng_Latn" in data
            assert "rus_Cyrl" in data
            assert "fra_Latn" not in data
        finally:
            app.dependency_overrides.clear()

    def test_languages_endpoint_former_members(self, client):
        """Test languages endpoint with former_members level."""
        mock_engine = MagicMock(spec=TranslationEngineProtocol)
        mock_engine.languages = {
            "eng_Latn": {"en": "English", "ord": 1},
            "rus_Cyrl": {"en": "Russian", "ord": 50},
            "fra_Latn": {"en": "French", "ord": 100},
        }

        def override_get_translator_engine():
            return mock_engine

        app.dependency_overrides[get_translator_engine] = override_get_translator_engine

        try:
            response = client.get("/languages?language_level=former_members")

            assert response.status_code == 200
            data = response.json()
            # Should include languages with ord < 100
            assert "eng_Latn" in data
            assert "rus_Cyrl" in data
            assert "fra_Latn" not in data
        finally:
            app.dependency_overrides.clear()

    def test_languages_endpoint_all(self, client):
        """Test languages endpoint with all level."""
        mock_engine = MagicMock(spec=TranslationEngineProtocol)
        mock_engine.languages = {
            "eng_Latn": {"en": "English", "ord": 1},
            "rus_Cyrl": {"en": "Russian", "ord": 50},
            "fra_Latn": {"en": "French", "ord": 100},
        }

        def override_get_translator_engine():
            return mock_engine

        app.dependency_overrides[get_translator_engine] = override_get_translator_engine

        try:
            response = client.get("/languages?language_level=all")

            assert response.status_code == 200
            data = response.json()
            # Should include all languages
            assert "eng_Latn" in data
            assert "rus_Cyrl" in data
            assert "fra_Latn" in data
        finally:
            app.dependency_overrides.clear()

    def test_languages_endpoint_default_level(self, client):
        """Test languages endpoint with default level (members_only)."""
        mock_engine = MagicMock(spec=TranslationEngineProtocol)
        mock_engine.languages = {
            "eng_Latn": {"en": "English", "ord": 1},
            "fra_Latn": {"en": "French", "ord": 10},
        }

        def override_get_translator_engine():
            return mock_engine

        app.dependency_overrides[get_translator_engine] = override_get_translator_engine

        try:
            response = client.get("/languages")

            assert response.status_code == 200
            data = response.json()
            assert "eng_Latn" in data
            assert "fra_Latn" not in data
        finally:
            app.dependency_overrides.clear()
