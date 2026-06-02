"""Декомпозиция большого интеграционного теста test_markdown_translator_full_pipeline.

Эти тесты покрывают все частные случаи из большого интеграционного теста,
но каждый тестирует конкретный аспект изолированно.
"""


class TestFullPipelineDecomposition:
    """Декомпозиция большого интеграционного теста test_markdown_translator_full_pipeline.

    Эти тесты покрывают все частные случаи из большого интеграционного теста,
    но каждый тестирует конкретный аспект изолированно.
    """

    def test_front_matter_from_full_test(self, mock_translator):
        """Front matter из полного интеграционного теста."""
        source_markdown = "---\ntitle: Document\nlayout: post\n---\n\nContent."

        translation_dict = {"Content.": "Контент."}

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert result.startswith("---"), "Front matter не начинается с ---"
        assert "title: Document" in result, "title потерян"
        assert "layout: post" in result, "layout потерян"

    def test_heading_and_paragraph_from_full_test(self, mock_translator):
        """Заголовок H2 и абзац из полного теста."""
        source_markdown = "## Some text before.\n\nParagraph text."

        translation_dict = {
            "Some text before.": "Некоторый текст перед.",
            "Paragraph text.": "Текст абзаца.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "##" in result, "Заголовок H2 потерян"
        assert "Некоторый текст перед." in result, "Заголовок не переведён"

    def test_inline_elements_from_full_test(self, mock_translator):
        """Жирный текст и ссылка из полного теста."""
        source_markdown = "This is **bold** text. Go to [Google](https://google.com)."

        translation_dict = {
            "This is {s_1}bold{/s_1} text.": "Это {s_1}жирный{/s_1} текст.",
            "Go to {lnk_1}Google{/lnk_1}.": "Перейдите в {lnk_1}Google{/lnk_1}.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "**" in result, "Жирный текст не восстановлен"
        assert "[Google]" in result or "Google" in result, "Ссылка потеряна"
        assert "https://google.com" in result, "URL ссылки потерян"

    def test_nested_lists_from_full_test(self, mock_translator):
        """Вложенные списки из полного теста."""
        source_markdown = "- Item 1\n    - Nested Item 1.1"

        translation_dict = {
            "Item 1": "Элемент 1",
            "Nested Item 1.1": "Вложенный элемент 1.1",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) >= 2, "Элементы списка потеряны"
        assert any(l.startswith("    -") for l in lines), (
            "Отступ вложенного списка потерян"
        )

    def test_definition_list_from_full_test(self, mock_translator):
        """Список определений из полного теста."""
        source_markdown = "Term text\n: Definition text"

        translation_dict = {
            "Term text": "Текст термина",
            "Definition text": "Текст определения",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert ":" in result, "Маркер определения потерян"

    def test_code_in_blockquote_from_full_test(self, mock_translator):
        """Код в цитате из полного теста."""
        source_markdown = "> ```python\ndef hello():\n    print('world')\n```"

        translation_dict = {}

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert ">" in result, "Цитата потеряна"
        assert "```" in result, "Блок кода потерян"
        assert "python" in result, "Язык кода потерян"

    def test_table_from_full_test(self, mock_translator):
        """Таблица из полного теста."""
        source_markdown = (
            "| Name | Age |\n|------|-----|\n| John | 30  |\n| Jane | 25  |"
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

        assert "|" in result, "Таблица потеряна"
        assert result.count("|") >= 6, "Структура таблицы повреждена"

    def test_task_list_from_full_test(self, mock_translator):
        """Task list из полного теста."""
        source_markdown = "- [x] Done task\n- [ ] Pending task"

        translation_dict = {
            "{chk_1}Done task": "{chk_1}Выполнена",
            "{chk_2}Pending task": "{chk_2}В ожидании",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "- [x]" in result or "[x]" in result, "Отмеченная задача потеряна"
        assert "- [ ]" in result or "[ ]" in result, "Неотмеченная задача потеряна"

    def test_final_paragraph_from_full_test(self, mock_translator):
        """Финальный абзац из полного теста."""
        source_markdown = "Some text after."

        translation_dict = {
            "Some text after.": "Некоторый текст после.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "Некоторый текст после." in result, "Финальный абзац не переведён"

    # 1. Тест таблицы с проверкой структуры
    def test_table_structure_preserved(self, mock_translator):
        """Таблица должна сохранять все | разделители."""
        source = "| A | B |\n|---|---|\n| 1 | 2 |"
        translation_dict = {"A": "А", "B": "Б", "1": "1", "2": "2"}
        translator = mock_translator(source, translation_dict)
        result = translator.process()

        assert result.count("|") >= 8, "Разделители таблицы потеряны"
        assert "|------|" in result or "|---|" in result, (
            "Разделительная строка повреждена"
        )

    # 2. Тест task list с checkbox
    def test_task_list_checkbox_preserved(self, mock_translator):
        """Checkbox должен сохраняться как [- [x]] или [- [ ]]."""
        source = "- [x] Task"
        translation_dict = {"{html_1} Task": "{html_1} Задача"}
        translator = mock_translator(source, translation_dict)
        result = translator.process()

        # Не должно быть дублирования "- -"
        assert not result.startswith("- -"), "Дублируется маркер списка"
        assert "[x]" in result, "Checkbox потерян"

    # 3. Тест code в blockquote
    def test_code_fence_in_blockquote(self, mock_translator):
        """Fence внутри blockquote должен сохранять > префикс."""
        source = "> ```python\ncode\n```"
        translator = mock_translator(source, {})
        result = translator.process()

        assert ">" in result, "Цитата потеряна"
        assert "```" in result, "Fence потерян"
        # Код должен быть внутри цитаты
        lines = result.split("\n")
        code_lines = [l for l in lines if "code" in l]
        assert all(l.startswith(">") for l in code_lines), "Код вне цитаты"

    # 4. Тест spacing между блоками
    def test_spacing_between_blocks(self, mock_translator):
        """Между заголовком и параграфом должен быть пустой строка."""
        source = "## Title\n\nParagraph"
        translation_dict = {"Title": "Заголовок", "Paragraph": "Абзац"}
        translator = mock_translator(source, translation_dict)
        result = translator.process()

        assert "\n\n" in result, "Отсутствует разделение между блоками"

    # 5. Тест inline элементов (bold + link)
    def test_inline_bold_link_restoration(self, mock_translator):
        """Bold и ссылка должны восстанавливаться корректно."""
        source = "**bold** and [link](http://test.com)"
        translation_dict = {
            "{s_1}bold{/s_1}": "{s_1}жирный{/s_1}",
            "{lnk_1}link{/lnk_1}": "{lnk_1}ссылка{/lnk_1}",
        }
        translator = mock_translator(source, translation_dict)
        result = translator.process()

        assert "**" in result, "Bold не восстановлен"
        assert "[" in result and "]" in result, "Ссылка не восстановлена"
        assert "http://test.com" in result, "URL потерян"
