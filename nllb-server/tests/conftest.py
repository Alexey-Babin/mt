# tests/conftest.py
import pytest

from mt_server.engine import Translator


@pytest.fixture(scope="session")
def translator():
    return Translator("/opt/mt/models/nllb-200-distilled-600M")
