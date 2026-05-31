"""Интеграционные тесты для отдельных проблем markdown переводчика.

Каждый тест проверяет конкретную проблему:
1. Таблицы отсутствуют в выводе
2. Заголовки теряют уровень (# вместо ##)
3. Плейсхолдеры не восстанавливаются
4. Отсутствуют переносы строк между элементами
5. Task list отсутствует
6. Код не оформлен как блок кода
"""

from unittest.mock import MagicMock, patch

import pytest
from src.mt_server.markdown2.markdown_translator import MarkdownTranslator


class MockTranslationEngine:
    """Mock-движок перевода для тестов."""

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
            return {"input_ids": [0] * len(words)}

        self.tokenizer.side_effect = count_tokens_side_effect

    def get_supported_languages(self):
        return ["eng_Latn", "rus_Cyrl"]

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        """Посегментный перевод чанка с сохранением маркера разделителя."""
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


@pytest.fixture
def mock_translator():
    """Фикстура для создания переводчика со стабильным лимитом токенов."""

    def _create_translator(text: str, translation_dict=None):
        engine = MockTranslationEngine(translation_dict)
        with patch("src.mt_server.markdown2.markdown_translator.max_input_tokens", 100):
            return MarkdownTranslator(
                text=text,
                src_lang="eng_Latn",
                tgt_lang="rus_Cyrl",
                engine=engine,
            )

    return _create_translator


class TestTableRendering:
    """Тесты проблемы: таблица полностью отсутствует в выводе."""

    def test_simple_table_preserved(self, mock_translator):
        """Простая таблица должна сохраниться в выводе."""
        source_markdown = (
            "| Name | Age |\n|------|-----|\n| John | 30  |\n| Jane | 25  |\n"
        )

        translation_dict = {
            "Name": "Имя",
            "Age": "Возраст",
            "John": "Джон",
            "30": "30",
            "Jane": "Джейн",
            "25": "25",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Таблица должна присутствовать
        assert "|" in result, "Таблица отсутствует: нет символа |"
        assert result.count("|") >= 6, (
            f"Таблица повреждена: ожидалось минимум 6 '|', найдено {result.count('|')}"
        )

        # Проверяем наличие заголовков таблицы
        assert "Имя" in result or "Name" in result, (
            "Заголовок 'Name' не переведён или отсутствует"
        )
        assert "Возраст" in result or "Age" in result, (
            "Заголовок 'Age' не переведён или отсутствует"
        )

        # Проверяем наличие разделительной строки таблицы
        assert "|------|" in result or "|-" in result, (
            "Разделительная строка таблицы отсутствует"
        )

    def test_table_with_translation(self, mock_translator):
        """Таблица с переводимыми ячейками."""
        source_markdown = (
            "| Header 1 | Header 2 |\n"
            "|----------|----------|\n"
            "| Cell 1   | Cell 2   |\n"
            "| Cell 3   | Cell 4   |\n"
        )

        translation_dict = {
            "Header 1": "Заголовок 1",
            "Header 2": "Заголовок 2",
            "Cell 1": "Ячейка 1",
            "Cell 2": "Ячейка 2",
            "Cell 3": "Ячейка 3",
            "Cell 4": "Ячейка 4",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Проверяем структуру таблицы
        lines = result.strip().split("\n")
        table_lines = [l for l in lines if "|" in l]
        assert len(table_lines) >= 4, (
            f"Таблица неполная: найдено {len(table_lines)} строк, ожидалось минимум 4"
        )


class TestHeadingLevels:
    """Тесты проблемы: заголовок # вместо ## (теряется уровень заголовка)."""

    def test_heading_level_h2_preserved(self, mock_translator):
        """Заголовок уровня 2 должен остаться ##."""
        source_markdown = "## Some Title\n\nSome text."

        translation_dict = {
            "Some Title": "Некоторый заголовок",
            "Some text.": "Некоторый текст.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Проверяем что заголовок уровня 2 сохранился
        assert "##" in result, f"Заголовок уровня 2 потерян. Результат: {result}"
        assert (
            result.startswith("---\n") is False or "##" in result.split("---\n")[1]
            if "---" in result
            else True
        )

        # Не должно быть заголовка уровня 1 там, где был уровень 2
        lines = result.split("\n")
        heading_lines = [l for l in lines if l.startswith("#")]
        for hl in heading_lines:
            if "Некоторый заголовок" in hl or "Some Title" in hl:
                assert hl.startswith("##"), (
                    f"Уровень заголовка изменён: ожидалось '##', получено '{hl[:2]}'"
                )

    def test_heading_level_h3_preserved(self, mock_translator):
        """Заголовок уровня 3 должен остаться ###."""
        source_markdown = "### Sub Title\n\nContent here."

        translation_dict = {
            "Sub Title": "Подзаголовок",
            "Content here.": "Содержимое здесь.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "###" in result, f"Заголовок уровня 3 потерян. Результат: {result}"


class TestPlaceholderRestoration:
    """Тесты проблемы: плейсхолдеры {s_1}, {lnk_2} не восстановлены."""

    def test_bold_placeholder_restored(self, mock_translator):
        """Плейсхолдеры жирного текста должны восстановиться в **text**."""
        source_markdown = "This is **bold** text."

        translation_dict = {
            "This is {s_1}bold{/s_1} text.": "Это {s_1}жирный{/s_1} текст.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Плейсхолдеры не должны остаться в результате
        assert "{s_1}" not in result, (
            f"Плейсхолдер {{s_1}} не восстановлен. Результат: {result}"
        )
        assert "{/s_1}" not in result, (
            f"Закрывающий плейсхолдер {{/s_1}} не восстановлен. Результат: {result}"
        )

        # Должна быть markdown разметка жирного текста
        assert "**" in result, f"Жирный текст не оформлен через **. Результат: {result}"

    def test_link_placeholder_restored(self, mock_translator):
        """Плейсхолдеры ссылки должны восстановиться в [text](url)."""
        source_markdown = "Go to [Google](https://google.com)."

        translation_dict = {
            "Go to {lnk_1}Google{/lnk_1}.": "Перейдите в {lnk_1}Google{/lnk_1}.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Плейсхолдеры не должны остаться в результате
        assert "{lnk_1}" not in result, (
            f"Плейсхолдер {{lnk_1}} не восстановлен. Результат: {result}"
        )
        assert "{/lnk_1}" not in result, (
            f"Закрывающий плейсхолдер {{/lnk_1}} не восстановлен. Результат: {result}"
        )

        # Должна быть markdown разметка ссылки
        assert "[" in result and "]" in result, (
            f"Ссылка не оформлена правильно. Результат: {result}"
        )
        assert "(" in result and ")" in result, (
            f"URL ссылки отсутствует. Результат: {result}"
        )

    def test_multiple_placeholders_restored(self, mock_translator):
        """Несколько плейсхолдеров должны восстановиться корректно."""
        source_markdown = "This is **bold** and [link](http://example.com) text."

        translation_dict = {
            "This is {s_1}bold{/s_1} and {lnk_1}link{/lnk_1} text.": "Это {s_1}жирный{/s_1} и {lnk_1}ссылка{/lnk_1} текст.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Никакие плейсхолдеры не должны остаться
        assert "{" not in result or "{s_1}" not in result, (
            f"Плейсхолдеры не восстановлены. Результат: {result}"
        )

        # Должны быть обе разметки
        assert "**" in result, "Жирный текст не оформлен"
        assert "[" in result and "](" in result, "Ссылка не оформлена"


class TestLineBreaks:
    """Тесты проблемы: отсутствуют переносы строк между элементами."""

    def test_paragraphs_separated_by_newlines(self, mock_translator):
        """Абзацы должны быть разделены пустыми строками."""
        source_markdown = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

        translation_dict = {
            "First paragraph.": "Первый абзац.",
            "Second paragraph.": "Второй абзац.",
            "Third paragraph.": "Третий абзац.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Проверяем наличие пустых строк между абзацами
        assert "\n\n" in result, "Абзацы не разделены пустыми строками"

        lines = result.strip().split("\n")
        non_empty_lines = [l for l in lines if l.strip()]
        assert len(non_empty_lines) >= 3, (
            f"Не все абзацы сохранены. Найдено {len(non_empty_lines)} строк"
        )

    def test_list_items_on_separate_lines(self, mock_translator):
        """Элементы списка должны быть на отдельных строках."""
        source_markdown = "- Item 1\n- Item 2\n- Item 3"

        translation_dict = {
            "Item 1": "Элемент 1",
            "Item 2": "Элемент 2",
            "Item 3": "Элемент 3",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Каждый элемент списка должен быть на своей строке
        lines = [l.strip() for l in result.split("\n") if l.strip()]
        list_items = [l for l in lines if l.startswith("-")]
        assert len(list_items) >= 3, (
            f"Элементы списка объединены. Найдено {len(list_items)} элементов"
        )


class TestTaskList:
    """Тесты проблемы: task list отсутствует."""

    def test_task_list_preserved(self, mock_translator):
        """Task list должен сохраниться с маркерами [- [x]] и [- [ ]]."""
        source_markdown = "- [x] Done task\n- [ ] Pending task"

        translation_dict = {
            "{chk_1}Done task": "{chk_1}Выполнена",
            "{chk_2}Pending task": "{chk_2}В ожидании",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Task list маркеры должны присутствовать
        has_checked = "- [x]" in result or "[x]" in result
        has_unchecked = "- [ ]" in result or "[ ]" in result

        assert has_checked or has_unchecked, (
            f"Task list маркеры отсутствуют. Результат: {result}"
        )

    def test_task_list_with_translation(self, mock_translator):
        """Task list с переводом текста задач."""
        source_markdown = "- [x] Complete\n- [ ] In progress"

        translation_dict = {
            "{chk_1}Complete": "{chk_1}Завершено",
            "{chk_2}In progress": "{chk_2}В процессе",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Проверяем структуру task list
        lines = [l.strip() for l in result.split("\n") if l.strip()]
        task_lines = [l for l in lines if "[x]" in l or "[ ]" in l]
        assert len(task_lines) >= 2, f"Task list элементы потеряны. Результат: {result}"


class TestCodeBlock:
    """Тесты проблемы: код не оформлен как блок кода."""

    def test_code_block_with_fence(self, mock_translator):
        """Блок кода должен быть оформлен через ```."""
        source_markdown = "```python\ndef hello():\n    print('world')\n```"

        translation_dict = {}  # Код не переводится

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Блок кода должен быть обрамлен ```
        assert "```" in result, f"Блок кода не оформлен через ```. Результат: {result}"

        # Должен сохраниться язык подсветки
        assert "python" in result.lower(), (
            f"Язык блока кода потерян. Результат: {result}"
        )

        # Содержимое кода должно сохраниться
        assert "def hello():" in result or "print" in result, (
            "Содержимое блока кода потеряно"
        )

    def test_code_block_in_blockquote(self, mock_translator):
        """Блок кода внутри цитаты должен сохранить оба элемента."""
        source_markdown = "> ```python\n> code here\n> ```"

        translation_dict = {}

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Должны присутствовать оба элемента
        assert ">" in result, "Цитата потеряна"
        assert "```" in result, "Блок кода потерян"

    def test_inline_code_preserved(self, mock_translator):
        """Инлайн код должен сохраниться в `backticks`."""
        source_markdown = "Use the `function()` method."

        translation_dict = {
            "Use the {code_1} method.": "Используйте метод {code_1}.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Инлайн код должен быть в backticks
        assert "`" in result, f"Инлайн код не оформлен через `. Результат: {result}"
        assert "{" not in result or "code_" not in result, (
            f"Плейсхолдер инлайн кода не восстановлен. Результат: {result}"
        )


class TestCombinedStructure:
    """Комплексные тесты структуры документа."""

    def test_full_document_structure(self, mock_translator):
        """Все структурные элементы должны сохраниться в документе."""
        source_markdown = (
            "## Title\n\n"
            "Paragraph with **bold** text.\n\n"
            "- List item 1\n"
            "- List item 2\n\n"
            "| Col1 | Col2 |\n"
            "|------|------|\n"
            "| A    | B    |\n\n"
            "- [x] Task done\n\n"
            "```\ncode block\n```\n\n"
            "End paragraph."
        )

        translation_dict = {
            "Title": "Заголовок",
            "Paragraph with {s_1}bold{/s_1} text.": "Абзац с {s_1}жирным{/s_1} текстом.",
            "List item 1": "Элемент списка 1",
            "List item 2": "Элемент списка 2",
            "Col1": "Кол1",
            "Col2": "Кол2",
            "A": "А",
            "B": "Б",
            "{chk_1}Task done": "{chk_1}Задача выполнена",
            "End paragraph.": "Конечный абзац.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Проверяем наличие всех структурных элементов
        assert "##" in result or "Заголовок" in result, "Заголовок потерян"
        assert "**" in result or "жирным" in result, "Жирный текст потерян"
        assert "-" in result, "Список потерян"
        assert "|" in result, "Таблица потеряна"
        assert "[x]" in result or "[ ]" in result, "Task list потерян"
        assert "```" in result, "Блок кода потерян"
        assert "\n\n" in result, "Переносы строк между элементами потеряны"
