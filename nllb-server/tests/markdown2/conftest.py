"""Общие фикстуры и mock-объекты для тестов markdown2."""

from unittest.mock import MagicMock

import pytest
from src.mt_server.markdown2.chunker import MarkdownChunker
from src.mt_server.markdown2.models.placeholder_codes import SEGMENT_SEPARATOR
from src.mt_server.markdown2.translator import MarkdownTranslator


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

        # Разделитель может быть SEGMENT_SEPARATOR (с пробелами) или "\x1e"
        if SEGMENT_SEPARATOR in text:
            separator = SEGMENT_SEPARATOR
        else:
            separator = "\x1e"

        segments = text.split(separator)
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

        return separator.join(translated_segments)

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
def integration_translation_dict():
    """Словарь переводов для интеграционного теста full_pipeline."""
    return {
        # Полный чанк со всеми сегментами, разделёнными SEGMENT_SEPARATOR и плейсхолдерами
        "Some text before. __S__ This is __B_O_1__ bold __B_C_1__  text. Go to __L_O_2__ Google __L_C_2__ . __S__ Item 1 __S__ Nested Item 1.1 __S__ Term text __S__ Definition text __S__ Name __S__ Age __S__ John __S__ 30 __S__ Jane __S__ 25 __S__ __T_1__  Done task __S__ __T_1__  Pending task __S__ Some text after.": "Некоторый текст перед. __S__ Это __B_O_1__ жирный __B_C_1__  текст. Перейдите на __L_O_2__ Google __L_C_2__ . __S__ Элемент 1 __S__ Вложенный элемент 1.1 __S__ Текст термина __S__ Текст определения __S__ Имя __S__ Возраст __S__ Джон __S__ 30 __S__ Джейн __S__ 25 __S__ __T_1__  Выполненная задача __S__ __T_1__  Ожидающая задача __S__ Некоторый текст после.",
        # Также поддерживаем посегментный перевод (для гибкости)
        "Some text before.": "Некоторый текст перед.",
        "This is __B_O_1__ bold __B_C_1__  text. Go to __L_O_2__ Google __L_C_2__ .": "Это __B_O_1__ жирный __B_C_1__  текст. Перейдите на __L_O_2__ Google __L_C_2__ .",
        "This is __B_O_1__ bold __B_C_1__  text.": "Это __B_O_1__ жирный __B_C_1__  текст.",
        "Go to __L_O_2__ Google __L_C_2__ .": "Перейдите на __L_O_2__ Google __L_C_2__ .",
        "Item 1": "Элемент 1",
        "Nested Item 1.1": "Вложенный элемент 1.1",
        "Term text": "Текст термина",
        "Definition text": "Текст определения",
        "Name": "Имя",
        "Age": "Возраст",
        "John": "Джон",
        "30": "30",
        "Jane": "Джейн",
        "25": "25",
        "__T_1__  Done task": "__T_1__  Выполненная задача",
        "__T_1__  Pending task": "__T_1__  Ожидающая задача",
        "Some text after.": "Некоторый текст после.",
    }


@pytest.fixture
def mock_translator(mock_engine, integration_translation_dict):
    """Фикстура для создания переводчика со стабильным лимитом токенов.

    По умолчанию использует лимит 100 токенов и словарь переводов для интеграционного теста.
    Для изменения используйте параметризованную версию mock_translator_with_limit.
    """

    def _create_translator(text: str, translation_dict=None):
        engine = mock_engine(translation_dict or integration_translation_dict)
        return MarkdownTranslator(
            text=text,
            src_lang="eng_Latn",
            tgt_lang="rus_Cyrl",
            engine=engine,  # type: ignore
            max_tokens=100,
        )

    return _create_translator


@pytest.fixture
def mock_translator_with_limit(mock_engine):
    """Фикстура для создания переводчика с кастомным лимитом токенов."""

    def _create_translator(text: str, max_tokens: int, translation_dict=None):
        engine = mock_engine(translation_dict)
        return MarkdownTranslator(
            text=text,
            src_lang="eng_Latn",
            tgt_lang="rus_Cyrl",
            engine=engine,  # type: ignore
            max_tokens=max_tokens,
        )

    return _create_translator
