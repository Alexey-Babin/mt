"""Unit-тесты для отдельных элементов markdown переводчика.

Эти тесты проверяют базовую функциональность:
- Таблицы
- Заголовки
- Плейсхолдеры (bold, link, code)
- Переносы строк
- Task list
- Блоки кода
- Front matter
- Списки определений
- Вложенные списки
- Ссылки
- Цитаты
"""

import pytest


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
        table_lines = [ln for ln in lines if "|" in ln]
        assert len(table_lines) >= 4, (
            f"Таблица неполная: найдено {len(table_lines)} строк, ожидалось минимум 4"
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
        lines = [ln.strip() for ln in result.split("\n") if ln.strip()]
        task_lines = [ln for ln in lines if "[x]" in ln or "[ ]" in ln]
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

    def test_inline_code_preserved(self, mock_translator):
        """Инлайн код должен сохраниться в `backticks`."""
        source_markdown = "Use the `function()` method."

        translation_dict = {
            "Use the __C_1__  method.": "Используйте метод __C_1__ .",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Инлайн код должен быть в backticks
        assert "`" in result, f"Инлайн код не оформлен через `. Результат: {result}"
        assert "{" not in result or "code_" not in result, (
            f"Плейсхолдер инлайн кода не восстановлен. Результат: {result}"
        )


class TestFrontMatter:
    """Тесты проблемы: front matter (YAML) не сохраняется."""

    def test_front_matter_preserved(self, mock_translator):
        """Front matter должен сохраниться в начале документа."""
        source_markdown = "---\ntitle: My Document\nauthor: John\n---\n\nContent."

        translation_dict = {"Content.": "Контент."}

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert result.startswith("---"), "Front matter не начинается с ---"
        assert "title: My Document" in result, "title потерян"
        assert "author: John" in result, "author потерян"
        assert result.rstrip().endswith("Контент.") or result.rstrip().endswith(
            "Content."
        ), "Контент после front matter потерян"

    def test_front_matter_not_translated(self, mock_translator):
        """Front matter не должен переводиться."""
        source_markdown = "---\ntitle: Документ\nlayout: пост\n---\n\nText."

        translation_dict = {"Text.": "Текст."}

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Front matter должен остаться без изменений
        assert "title: Документ" in result, "title в front matter изменён"
        assert "layout: пост" in result, "layout в front matter изменён"


class TestDefinitionLists:
    """Тесты проблемы: списки определений теряются."""

    def test_definition_list_preserved(self, mock_translator):
        """Список определений должен сохраниться с маркером :."""
        source_markdown = "Term\n: Definition"

        translation_dict = {
            "Term": "Термин",
            "Definition": "Определение",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert ":" in result, "Маркер определения потерян"
        assert "Термин" in result or "Term" in result, "Термин потерян"
        assert "Определение" in result or "Definition" in result, "Определение потеряно"


class TestNestedLists:
    """Тесты проблемы: вложенные списки теряют структуру."""

    def test_nested_list_indent_preserved(self, mock_translator):
        """Вложенные списки должны сохранить отступы."""
        source_markdown = "- Item 1\n    - Nested Item 1.1\n    - Nested Item 1.2"

        translation_dict = {
            "Item 1": "Элемент 1",
            "Nested Item 1.1": "Вложенный элемент 1.1",
            "Nested Item 1.2": "Вложенный элемент 1.2",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        lines = [ln for ln in result.split("\n") if ln.strip()]
        assert len(lines) >= 3, "Элементы списка потеряны"

        # Проверяем наличие вложенных элементов с отступом
        nested_items = [ln for ln in lines if ln.startswith("    -")]
        assert len(nested_items) >= 2, (
            f"Вложенные элементы потеряны. Найдено: {len(nested_items)}"
        )


class TestLinkPreservation:
    """Тесты проблемы: ссылки теряют URL или текст."""

    def test_link_url_preserved(self, mock_translator):
        """URL ссылки должен сохраниться."""
        source_markdown = "Visit [Example](https://example.com)."

        translation_dict = {
            "Visit __L_O_1__ Example __L_C_1__ .": "Посетите __L_O_1__ Example __L_C_1__ ."
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "https://example.com" in result, "URL ссылки потерян"
        assert "[Example]" in result or "Example" in result, "Текст ссылки потерян"

    def test_link_text_translated(self, mock_translator):
        """Текст ссылки должен переводиться."""
        source_markdown = "Go to [Google](https://google.com)."

        translation_dict = {
            "Go to __L_O_1__ Google __L_C_1__ .": "Перейдите на __L_O_1__ Google __L_C_1__ ."
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "Перейдите" in result or "Go to" not in result, (
            "Текст перед ссылкой не переведён"
        )


class TestBlockquotes:
    """Тесты проблемы: цитаты (blockquote) повреждаются."""

    def test_blockquote_preserved(self, mock_translator):
        """Цитата должна сохраниться с маркером >."""
        source_markdown = "> This is a quote."

        translation_dict = {"This is a quote.": "Это цитата."}

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert ">" in result, "Маркер цитаты потерян"
        assert "Это цитата." in result or "This is a quote." in result, (
            "Содержимое цитаты потеряно"
        )

    def test_multiline_blockquote(self, mock_translator):
        """Многострочная цитата должна сохраниться."""
        source_markdown = "> Line 1.\n> Line 2.\n> Line 3."

        translation_dict = {
            "Line 1.": "Строка 1.",
            "Line 2.": "Строка 2.",
            "Line 3.": "Строка 3.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        lines = result.split("\n")
        quote_lines = [ln for ln in lines if ln.strip().startswith(">")]
        assert len(quote_lines) >= 3, (
            f"Строки цитаты потеряны. Найдено: {len(quote_lines)}"
        )


class TestMultipleHeadings:
    """Тесты проблемы: несколько заголовков разного уровня."""

    def test_multiple_heading_levels(self, mock_translator):
        """Заголовки разных уровней должны сохраниться."""
        source_markdown = "# H1\n## H2\n### H3\n#### H4"

        translation_dict = {
            "H1": "Заголовок 1",
            "H2": "Заголовок 2",
            "H3": "Заголовок 3",
            "H4": "Заголовок 4",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "#" in result, "Заголовки потеряны"
        assert "##" in result, "Заголовок H2 потерян"
        assert "###" in result, "Заголовок H3 потерян"
        assert "####" in result, "Заголовок H4 потерян"


class TestMixedInlineElements:
    """Тесты проблемы: комбинации инлайн элементов."""

    def test_bold_and_italic(self, mock_translator):
        """Жирный и курсив должны сосуществовать."""
        source_markdown = "This is **bold** and *italic* text."

        translation_dict = {
            "This is __B_O_1__ bold __B_C_1__  and __I_O_2__ italic __I_C_2__  text.": "Это __B_O_1__ жирный __B_C_1__  и __I_O_2__ курсив __I_C_2__  текст."
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "**" in result, "Жирный текст не оформлен"
        assert "*" in result, "Курсив не оформлен"

    def test_link_and_code(self, mock_translator):
        """Ссылка и инлайн код должны сосуществовать."""
        source_markdown = "Use `func()` or visit [Docs](https://docs.example.com)."

        translation_dict = {
            "Use __C_1__  or visit __L_O_2__ Docs __L_C_2__ .": "Используйте __C_1__  или посетите __L_O_2__ Docs __L_C_2__ ."
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "`" in result, "Инлайн код не оформлен"
        assert "[" in result and "](" in result, "Ссылка не оформлена"


class TestEmptyInputs:
    """Тесты с пустыми и граничными входами."""

    @pytest.mark.parametrize(
        "source_markdown,translation_dict,check_fn",
        [
            # Пустая строка
            ("", {}, lambda r: r == ""),
            # Только пробелы
            ("   \n\n   ", {}, lambda r: isinstance(r, str)),
            # Одно слово
            ("Hello", {"Hello": "Привет"}, lambda r: "Привет" in r or "Hello" in r),
        ],
    )
    def test_empty_and_boundary_inputs(
        self, mock_translator, source_markdown, translation_dict, check_fn
    ):
        """Параметризованный тест для пустых и граничных входов."""
        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()
        assert check_fn(result), (
            f"Проверка не пройдена для input: {source_markdown!r}, result: {result!r}"
        )


class TestPlaceholderSpacing:
    """Регрессионные тесты: все плейсхолдеры в extracted_text отделены пробелами.

    NLLB должна видеть каждый плейсхолдер как отдельный токен,
    поэтому плейсхолдеры не должны прилипать к тексту.
    """

    def _get_extracted_texts(self, markdown: str) -> list[str]:
        from src.mt_server.markdown2.ast_walker import ASTWalker
        from src.mt_server.markdown2.parser import create_markdown_parser
        from markdown_it.tree import SyntaxTreeNode

        parser = create_markdown_parser()
        walker = ASTWalker()
        tokens = parser.parse(markdown)
        tree = SyntaxTreeNode(tokens)
        walker.walk(tree)
        return [u.extracted_text for u in walker.units if u.extracted_text.strip()]

    def test_bold_text_has_spaces_around_placeholders(self):
        """Жирный текст: плейсхолдеры отделены пробелами."""
        texts = self._get_extracted_texts("**bold text**")
        assert len(texts) == 1
        text = texts[0]
        # Плейсхолдеры должны быть отделены пробелами
        assert "__B_O_1__ " in text, f"Открывающий плейсхолдер не отделён: {text!r}"
        assert " __B_C_1__" in text, f"Закрывающий плейсхолдер не отделён: {text!r}"

    def test_inline_code_has_spaces_around_placeholder(self):
        """Инлайн-код: плейсхолдер отделён пробелами."""
        texts = self._get_extracted_texts("Use `code` here")
        assert len(texts) == 1
        text = texts[0]
        assert " __C_1__ " in text, f"Плейсхолдер кода не отделён: {text!r}"

    def test_link_has_spaces_around_placeholders(self):
        """Ссылка: плейсхолдеры отделены пробелами."""
        texts = self._get_extracted_texts("Click [link](url) now")
        assert len(texts) == 1
        text = texts[0]
        assert "__L_O_1__ " in text, f"Открывающий плейсхолдер ссылки не отделён: {text!r}"
        assert " __L_C_1__" in text, f"Закрывающий плейсхолдер ссылки не отделён: {text!r}"

    def test_no_placeholder_stuck_to_text(self):
        """Ни один плейсхолдер не должен прилипать к буквам/цифрам."""
        import re

        markdown = "This is **bold** and *italic* with `code` and [link](url)."
        texts = self._get_extracted_texts(markdown)

        placeholder_pattern = re.compile(r"__[A-Z](?:_[OC])?_\d+__")
        for text in texts:
            for match in placeholder_pattern.finditer(text):
                start, end = match.start(), match.end()
                # Символ ДО плейсхолдера (если есть) должен быть пробелом
                if start > 0:
                    assert text[start - 1] == " ", (
                        f"Плейсхолдер {match.group()} прилип к тексту слева: "
                        f"...{text[max(0, start - 5):end + 5]}..."
                    )
                # Символ ПОСЛЕ плейсхолдера (если есть) должен быть пробелом
                if end < len(text):
                    assert text[end] == " ", (
                        f"Плейсхолдер {match.group()} прилип к тексту справа: "
                        f"...{text[max(0, start - 5):end + 5]}..."
                    )
