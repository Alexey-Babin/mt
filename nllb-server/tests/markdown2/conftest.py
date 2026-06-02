"""Общие фикстуры и mock-объекты для тестов markdown2."""

from unittest.mock import MagicMock, patch

import pytest
from src.mt_server.markdown2.chunker import MarkdownChunker
from src.mt_server.markdown2.markdown_translator import MarkdownTranslator


class MockTranslationEngine:
    """Универсальный Mock-движок перевода для тестов.

    Поддерживает передачу словаря переводов и частичное совпадение ключей.
    """

    def __init__(self, translation_dict=None):
        self.model_name = "mock-nllb-model"
        self.has_cuda = False
        self.device = "cpu"
        self.languages = {"eng_Latn": "English", "rus_Cyrl": "Russian"}
        self.tokenizer = MagicMock()
        self._translation_dict = translation_dict or {}
        self._setup_tokenizer_mock()

    def _setup_tokenizer_mock(self):
        """Настраивает MagicMock токенизатора."""

        def count_tokens_side_effect(text: str, **kwargs):
            words = [w for w in text.split() if w]
            total_tokens = 0
            for w in words:
                if w.startswith("{") and len(w) > 10:
                    total_tokens += 5
                else:
                    total_tokens += 1
            return {"input_ids": [0] * total_tokens}

        self.tokenizer.side_effect = count_tokens_side_effect

    def get_supported_languages(self):
        return ["eng_Latn", "rus_Cyrl"]

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        """Посегментный перевод чанка с сохранением маркера разделителя."""
        # Сначала пробуем найти полное совпадение всего текста
        if text in self._translation_dict:
            return self._translation_dict[text]

        segments = [s.strip() for s in text.split("\x1e")]
        translated_segments = []

        for seg in segments:
            if seg in self._translation_dict:
                translated_segments.append(self._translation_dict[seg])
            else:
                # Если сегмент не найден, пробуем найти частичное совпадение
                found = False
                for key, value in self._translation_dict.items():
                    if key in seg:
                        translated_segments.append(seg.replace(key, value))
                        found = True
                        break
                if not found:
                    translated_segments.append(seg)

        return "\x1e".join(translated_segments)

    def validate_language(self, lang: str) -> None:
        pass


class MockTokenizer:
    """Имитатор токенизатора для тестов chunker."""

    def __call__(self, text: str, **kwargs):
        words = [w for w in text.split() if w]
        total_tokens = 0
        for w in words:
            if w.startswith("{") and len(w) > 10:
                total_tokens += 5
            else:
                total_tokens += 1
        return {"input_ids": [0] * total_tokens}


@pytest.fixture
def tokenizer():
    """Фикстура токенизатора для тестов chunker."""
    return MockTokenizer()


@pytest.fixture
def chunker(tokenizer):
    """Фикстура chunker с лимитом 50 токенов."""
    return MarkdownChunker(
        tokenizer=tokenizer, max_tokens=50, nllb_lang_code="rus_Cyrl"
    )


@pytest.fixture
def mock_engine():
    """Фикстура для создания mock-движка с кастомным словарём переводов."""

    def _create_engine(translation_dict=None):
        return MockTranslationEngine(translation_dict)

    return _create_engine


@pytest.fixture
def mock_translator():
    """Фикстура для создания переводчика со стабильным лимитом токенов.

    По умолчанию использует лимит 100 токенов. Для изменения используйте
    параметризованную версию mock_translator_with_limit.
    """

    def _create_translator(text: str, translation_dict=None):
        engine = MockTranslationEngine(translation_dict)
        with patch("src.mt_server.markdown2.markdown_translator.max_input_tokens", 100):
            return MarkdownTranslator(
                text=text,
                src_lang="eng_Latn",
                tgt_lang="rus_Cyrl",
                engine=engine,  # type: ignore
            )

    return _create_translator


@pytest.fixture
def mock_translator_with_limit():
    """Фикстура для создания переводчика с кастомным лимитом токенов."""

    def _create_translator(text: str, max_tokens: int, translation_dict=None):
        engine = MockTranslationEngine(translation_dict)
        with patch(
            "src.mt_server.markdown2.markdown_translator.max_input_tokens", max_tokens
        ):
            return MarkdownTranslator(
                text=text,
                src_lang="eng_Latn",
                tgt_lang="rus_Cyrl",
                engine=engine,  # type: ignore
            )

    return _create_translator
