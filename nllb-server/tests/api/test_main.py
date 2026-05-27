"""Tests for FastAPI endpoints in main.py"""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from mt_server.main import app
from mt_server.translation_service import TextFormat


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def _make_executor_mock():
    """Create a mock event loop where run_in_executor returns an awaitable."""

    async def async_wrapper(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    def sync_run_in_executor(executor, fn, *args, **kwargs):
        return async_wrapper(fn, *args, **kwargs)

    mock_loop = MagicMock()
    mock_loop.run_in_executor = MagicMock(side_effect=sync_run_in_executor)
    return mock_loop


class TestTranslateEndpoint:
    """Tests for /translate endpoint."""

    def test_translate_endpoint_success(self, client):
        """Test successful translation request."""
        with (
            patch("mt_server.main.translation_service") as mock_service,
            patch("mt_server.main.executor") as mock_executor,
            patch(
                "mt_server.main.asyncio.get_event_loop",
                return_value=_make_executor_mock(),
            ),
        ):
            mock_service.translate = MagicMock(return_value="Translated text")
            mock_executor.__class__ = ThreadPoolExecutor

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

    def test_translate_endpoint_empty_text(self, client):
        """Test translation with empty text returns 400."""
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

    def test_translate_endpoint_service_not_ready(self, client):
        """Test translation when service is not initialized."""
        with (
            patch("mt_server.main.translation_service", None),
            patch("mt_server.main.executor", None),
        ):
            response = client.post(
                "/translate",
                json={
                    "text": "Hello",
                    "src_lang": "eng_Latn",
                    "target_lang": "rus_Cyrl",
                },
            )

            assert response.status_code == 503
            assert response.json()["detail"] == "Translation service not ready"

    def test_translate_endpoint_executor_not_ready(self, client):
        """Test translation when executor is not initialized."""
        with (
            patch("mt_server.main.translation_service") as mock_service,
            patch("mt_server.main.executor", None),
        ):
            mock_service.translate = MagicMock(return_value="Translated text")

            response = client.post(
                "/translate",
                json={
                    "text": "Hello",
                    "src_lang": "eng_Latn",
                    "target_lang": "rus_Cyrl",
                },
            )

            assert response.status_code == 503
            assert response.json()["detail"] == "Executor not ready"

    def test_translate_endpoint_internal_error(self, client):
        """Test translation with internal error."""
        with (
            patch("mt_server.main.translation_service") as mock_service,
            patch("mt_server.main.executor") as mock_executor,
            patch(
                "mt_server.main.asyncio.get_event_loop",
                return_value=_make_executor_mock(),
            ),
        ):
            mock_service.translate = MagicMock(
                side_effect=Exception("Translation failed")
            )
            mock_executor.__class__ = ThreadPoolExecutor

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

    @pytest.mark.parametrize("format_value", ["auto", "plain", "markdown"])
    def test_translate_endpoint_with_different_formats(self, client, format_value):
        """Test translation with different format values."""
        with (
            patch("mt_server.main.translation_service") as mock_service,
            patch("mt_server.main.executor") as mock_executor,
            patch(
                "mt_server.main.asyncio.get_event_loop",
                return_value=_make_executor_mock(),
            ),
        ):
            mock_service.translate = MagicMock(return_value="Translated text")
            mock_executor.__class__ = ThreadPoolExecutor

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


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_endpoint_ready(self, client):
        """Test health check when service is ready."""
        with (
            patch("mt_server.main.translator_engine") as mock_engine,
            patch("mt_server.main.translation_service") as mock_service,
        ):
            mock_engine.model_name = "nllb-200-distilled-600M"
            mock_engine.has_cuda = True
            mock_engine.device = "cuda"

            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert data["model"] == "nllb-200-distilled-600M"
            assert data["gpu"] is True
            assert data["device"] == "cuda"

    def test_health_endpoint_loading(self, client):
        """Test health check when service is loading."""
        with (
            patch("mt_server.main.translator_engine", None),
            patch("mt_server.main.translation_service", None),
        ):
            response = client.get("/health")

            assert response.status_code == 200
            assert response.json()["status"] == "loading"


class TestLanguagesEndpoint:
    """Tests for /languages endpoint."""

    def test_languages_endpoint_members_only(self, client):
        """Test languages endpoint with members_only level."""
        with patch("mt_server.main.translator_engine") as mock_engine:
            mock_engine.languages = {
                "eng_Latn": {"en": "English", "ord": 1},
                "rus_Cyrl": {"en": "Russian", "ord": 2},
                "fra_Latn": {"en": "French", "ord": 10},
            }

            response = client.get("/languages?language_level=members_only")

            assert response.status_code == 200
            data = response.json()
            # Should only include languages with ord < 10
            assert "eng_Latn" in data
            assert "rus_Cyrl" in data
            assert "fra_Latn" not in data

    def test_languages_endpoint_former_members(self, client):
        """Test languages endpoint with former_members level."""
        with patch("mt_server.main.translator_engine") as mock_engine:
            mock_engine.languages = {
                "eng_Latn": {"en": "English", "ord": 1},
                "rus_Cyrl": {"en": "Russian", "ord": 50},
                "fra_Latn": {"en": "French", "ord": 100},
            }

            response = client.get("/languages?language_level=former_members")

            assert response.status_code == 200
            data = response.json()
            # Should include languages with ord < 100
            assert "eng_Latn" in data
            assert "rus_Cyrl" in data
            assert "fra_Latn" not in data

    def test_languages_endpoint_all(self, client):
        """Test languages endpoint with all level."""
        with patch("mt_server.main.translator_engine") as mock_engine:
            mock_engine.languages = {
                "eng_Latn": {"en": "English", "ord": 1},
                "rus_Cyrl": {"en": "Russian", "ord": 50},
                "fra_Latn": {"en": "French", "ord": 100},
            }

            response = client.get("/languages?language_level=all")

            assert response.status_code == 200
            data = response.json()
            # Should include all languages
            assert "eng_Latn" in data
            assert "rus_Cyrl" in data
            assert "fra_Latn" in data

    def test_languages_endpoint_default_level(self, client):
        """Test languages endpoint with default level (members_only)."""
        with patch("mt_server.main.translator_engine") as mock_engine:
            mock_engine.languages = {
                "eng_Latn": {"en": "English", "ord": 1},
                "fra_Latn": {"en": "French", "ord": 10},
            }

            response = client.get("/languages")

            assert response.status_code == 200
            data = response.json()
            assert "eng_Latn" in data
            assert "fra_Latn" not in data
