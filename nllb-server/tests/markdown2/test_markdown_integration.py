from unittest.mock import MagicMock, patch

import pytest

# Импортируем компоненты вашей архитектуры
from src.mt_server.markdown2.markdown_translator import MarkdownTranslator


class MockTranslationEngine:
    """Mock-движок перевода, полностью имитирующий инференс модели NLLB."""

    def __init__(self):
        self.model_name = "mock-nllb-model"
        self.has_cuda = False
        self.device = "cpu"
        self.languages = {"eng_Latn": "English", "rus_Cyrl": "Russian"}

        # Создаем MagicMock для токенизатора
        self.tokenizer = MagicMock()
        self._setup_tokenizer_mock()

        # Набор предопределенных переводов сегментов (включая маски плейсхолдеров)
        self._translation_dict = {
            "Some text before.": "Некоторый текст перед.",
            "This is {s_1}bold{/s_1} text.": "Это {s_1}жирный{/s_1} текст.",
            "Go to {lnk_1}Google{/lnk_1}.": "Перейдите в {lnk_1}Google{/lnk_1}.",
            "Item 1": "Элемент 1",
            "Nested Item 1.1": "Вложенный элемент 1.1",
            "Term text": "Текст термина",
            "Definition text": "Текст определения",
            "Some text after.": "Некоторый текст после.",
            "Name": "Имя",
            "Age": "Возраст",
            "John": "Джон",
            "30": "30",
            "Jane": "Джейн",
            "25": "25",
            "{chk_1}Done task": "{chk_1}Выполнена",
            "{chk_2}Pending task": "{chk_2}В ожидании",
        }

    def _setup_tokenizer_mock(self):
        """Настраивает MagicMock токенизатора, чтобы он детерминированно считал вес строк."""

        def count_tokens_side_effect(text: str, **kwargs):
            # Простой подсчет: 1 слово = 1 токен. Маски весят по 1 токену.
            words = [w for w in text.split() if w]
            return {"input_ids": [0] * len(words)}

        self.tokenizer.side_effect = count_tokens_side_effect

    def get_supported_languages(self):
        return ["eng_Latn", "rus_Cyrl"]

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        """Посегментный перевод чанка с сохранением маркера разделителя '\\x1e'."""
        segments = [s.strip() for s in text.split("\x1e")]
        translated_segments = []

        for seg in segments:
            if seg in self._translation_dict:
                translated_segments.append(self._translation_dict[seg])
            else:
                # Если сегмент не найден в словаре (или это служебный текст), возвращаем его как есть
                translated_segments.append(seg)

        # Склеиваем переведенные сегменты обратно через "\\x1e"
        return "\x1e".join(translated_segments)

    def validate_language(self, lang: str) -> None:
        pass


@pytest.fixture
def mock_translator():
    """Фикстура для создания переводчика со стабильным лимитом токенов."""
    engine = MockTranslationEngine()

    # С помощью patch переопределяем глобальную настройку max_input_tokens в процессе теста,
    # чтобы чанки резались предсказуемо независимо от файла config.py
    with patch("src.mt_server.markdown2.markdown_translator.max_input_tokens", 20):
        translator = MarkdownTranslator(
            translation_engine=engine,  # type: ignore
            src_lang="eng_Latn",
            tgt_lang="rus_Cyrl",
        )
        yield translator


def test_markdown_translator_full_pipeline(mock_translator):
    """Сквозной интеграционный тест полного цикла перевода сложного Markdown документа.

    Проверяет, что при переводе файла с определённой структурой (заголовки, списки,
    таблицы, task lists, код, цитаты), она сохранилась. Сам перевод mock-овый.
    """

    # 1. Формируем "грязный" исходный Markdown-текст на английском со всеми edge-cases
    source_markdown = (
        "---\n"
        "title: Document\n"
        "layout: post\n"
        "---\n\n"
        "## Some text before.\n\n"
        "This is **bold** text. Go to [Google](https://google.com).\n\n"
        "- Item 1\n"
        "    - Nested Item 1.1\n\n"
        "Term text\n"
        ": Definition text\n\n"
        "> ```python\n"
        "def hello():\n"
        "    print('world')\n"
        "```\n\n"
        "| Name | Age |\n"
        "|------|-----|\n"
        "| John | 30  |\n"
        "| Jane | 25  |\n\n"
        "- [x] Done task\n"
        "- [ ] Pending task\n\n"
        "Some text after."
    )

    # 2. Ожидаемый результат после перевода (структура должна сохраниться)
    expected_markdown = (
        "---\n"
        "title: Document\n"
        "layout: post\n"
        "---\n\n"
        "## Некоторый текст перед.\n\n"
        "Это **жирный** текст. Перейдите в [Google](https://google.com).\n\n"
        "- Элемент 1\n"
        "    - Вложенный элемент 1.1\n\n"
        "Текст термина\n"
        ": Текст определения\n\n"
        "> ```python\n"
        "def hello():\n"
        "    print('world')\n"
        "```\\n\\n"
        "| Имя | Возраст |\n"
        "|------|-----|\n"
        "| Джон | 30  |\n"
        "| Джейн | 25  |\n\n"
        "- [x] Выполнена\n"
        "- [ ] В ожидании\n\n"
        "Некоторый текст после."
    )

    # 3. Прогоняем через главный метод оркестратора
    result_markdown = mock_translator.process(source_markdown)

    # 4. Проверяем, что результат не пустой
    assert result_markdown is not None
    assert len(result_markdown) > 0

    # Проверяем наличие ключевых структурных элементов
    # Front matter должен сохраниться
    assert "---" in result_markdown
    assert "title: Document" in result_markdown

    # Таблица должна сохраниться
    assert "|" in result_markdown

    # Task list должен сохраниться
    assert "- [x]" in result_markdown or "- [ ]" in result_markdown

    # Код должен сохраниться
    assert "```" in result_markdown

    # Списки должны сохраниться
    assert "-" in result_markdown

    # Текст должен быть переведён (проверка наличия русского текста)
    assert "John" in result_markdown or "Джон" in result_markdown

    # Полное соответствие переведённого ожидаемому
    assert result_markdown == expected_markdown


@pytest.mark.parametrize("empty_input", ["", "   ", "\n\n"])
def test_markdown_translator_handles_empty_inputs(mock_translator, empty_input):
    """Интеграционный тест: пустые строки должны мгновенно возвращать пустую строку."""
    assert mock_translator.process(empty_input) == ""
