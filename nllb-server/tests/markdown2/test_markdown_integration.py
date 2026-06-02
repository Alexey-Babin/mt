from unittest.mock import MagicMock, patch

import pytest

# Импортируем компоненты вашей архитектуры
from src.mt_server.markdown2.markdown_translator import MarkdownTranslator


class MockTranslationEngine:
    """Mock-движок перевода, полностью имитирующий инференс модели NLLB.

    Содержит полный словарь переводов для всех сегментов интеграционного теста.
    """

    def __init__(self):
        self.model_name = "mock-nllb-model"
        self.has_cuda = False
        self.device = "cpu"
        self.languages = {"eng_Latn": "English", "rus_Cyrl": "Russian"}

        # Создаем MagicMock для токенизатора
        self.tokenizer = MagicMock()
        self._setup_tokenizer_mock()

        # Полный набор предопределенных переводов сегментов для интеграционного теста
        # Включает все возможные сегменты с учётом плейсхолдеров
        self._translation_dict = {
            # Заголовки и параграфы
            "Some text before.": "Некоторый текст перед.",
            # Параграф с inline элементами (плейсхолдеры будут подставлены walker'ом)
            "This is {s_1}bold{/s_1} text. Go to {lnk_1}Google{/lnk_1}.": "Это {s_1}жирный{/s_1} текст. Перейдите на {lnk_1}Google{/lnk_1}.",
            # Элементы списков
            "Item 1": "Элемент 1",
            "Nested Item 1.1": "Вложенный элемент 1.1",
            # Списки определений
            "Term text": "Текст термина",
            "Definition text": "Текст определения",
            # Код в цитате - переводим только содержимое кода (строки внутри fence)
            "def hello():": "def hello():  # функция приветствия",
            "    print('world')": "    print('мир')  # печатает мир",
            # Таблица - каждая ячейка отдельно
            "Name": "Имя",
            "Age": "Возраст",
            "John": "Джон",
            "30": "30",
            "Jane": "Джейн",
            "25": "25",
            # Task list с checkbox плейсхолдерами
            "{chk_1}Done task": "{chk_1}Выполненная задача",
            "{chk_2}Pending task": "{chk_2}Ожидающая задача",
            # Финальный параграф
            "Some text after.": "Некоторый текст после.",
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
                # Если сегмент не найден в словаре, возвращаем его как есть
                # Это позволяет обрабатывать служебные строки и код
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
    with patch("src.mt_server.markdown2.markdown_translator.max_input_tokens", 50):
        # Возвращаем фабрику для создания переводчика с конкретным текстом
        def _create_translator(text: str):
            return MarkdownTranslator(
                text=text,
                src_lang="eng_Latn",
                tgt_lang="rus_Cyrl",
                engine=engine,  # type: ignore
            )

        yield _create_translator


def test_markdown_translator_full_pipeline(mock_translator):
    """Сквозной интеграционный тест полного цикла перевода сложного Markdown документа.

    Проверяет, что при переводе файла с определённой структурой (заголовки, списки,
    таблицы, task lists, код в цитатах, списки определений), структура сохраняется,
    а контент переводится. Используется mock-движок с полным словарём переводов.

    Тест проверяет ПОЛНОЕ совпадение результата с ожидаемым Markdown.
    """

    # 1. Формируем исходный Markdown-текст на английском со всеми edge-cases
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
        "```python\n"
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

    # 2. Ожидаемый результат после перевода (структура сохранена, контент переведён)
    # Это ТО, ЧТО ДОЛЖНО ПОЛУЧИТЬСЯ при корректной работе системы
    expected_markdown = (
        "---\n"
        "title: Document\n"
        "layout: post\n"
        "---\n\n"
        "## Некоторый текст перед.\n\n"
        "Это **жирный** текст. Перейдите на [Google](https://google.com).\n\n"
        "- Элемент 1\n"
        "    - Вложенный элемент 1.1\n\n"
        "Текст термина\n"
        ": Текст определения\n\n"
        "```python\n"
        "def hello():\n"
        "    print('мир')\n"
        "```\n\n"
        "| Имя | Возраст |\n"
        "|------|------|\n"
        "| Джон | 30 |\n"
        "| Джейн | 25 |\n\n"
        "- [x] Выполненная задача\n"
        "- [ ] Ожидающая задача\n\n"
        "Некоторый текст после."
    )

    # 3. Создаем переводчик для конкретного текста и прогоняем через главный метод оркестратора
    translator = mock_translator(source_markdown)
    result_markdown = translator.process()

    # 4. Проверяем ПОЛНОЕ совпадение с ожидаемым результатом
    # Тест будет падать, пока не исправлены баги в reconstructor.py и ast_walker.py
    assert result_markdown == expected_markdown, (
        f"Результат перевода не совпадает с ожидаемым.\n\n"
        f"=== ОЖИДАЕМЫЙ ({len(expected_markdown)} символов) ===\n{expected_markdown}\n\n"
        f"=== ПОЛУЧЕНЫЙ ({len(result_markdown)} символов) ===\n{result_markdown}\n\n"
        f"=== РАЗНИЦА (посимвольно) ===\n"
        f"Длина ожидаемого: {len(expected_markdown)}, длина полученного: {len(result_markdown)}\n"
    )


@pytest.mark.parametrize("empty_input", ["", "   ", "\n\n"])
def test_markdown_translator_handles_empty_inputs(mock_translator, empty_input):
    """Интеграционный тест: пустые строки должны мгновенно возвращать пустую строку."""
    translator = mock_translator(empty_input)
    assert translator.process() == ""
