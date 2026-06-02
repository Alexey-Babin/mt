"""Тесты конкретных багов выявленных в test_markdown_translator_full_pipeline.

Эти тесты фокусируются на специфических багах которые приводят к падению
большого интеграционного теста. Каждый тест изолирует конкретную проблему.
"""


class TestFullPipelineIssues:
    """Тесты конкретных проблем выявленных в test_markdown_translator_full_pipeline.

    Эти тесты фокусируются на специфических багах которые приводят к падению
    большого интеграционного теста. Каждый тест изолирует конкретную проблему.
    """

    def test_paragraph_with_inline_elements_not_translated(self, mock_translator):
        """Баг: Абзац с inline элементами (bold, link) не переводится.

        Сценарий из большого теста:
        Input:  This is **bold** text. Go to [Google](https://google.com).
        Expected: Это **жирный** текст. Перейдите на [Google](https://google.com).
        Actual: This is **bold** text. Go to [Google](https://google.com) .

        Проблема: перевод не применяется к сегменту с плейсхолдерами.
        """
        source_markdown = "This is **bold** text. Go to [Google](https://google.com)."

        translation_dict = {
            r"This is {s_1}bold{/s_1} text.": r"Это {s_1}жирный{/s_1} текст.",
            r"Go to {lnk_2}Google{/lnk_2}.": r"Перейдите на {lnk_2}Google{/lnk_2}.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Ожидаем что текст будет переведён
        assert "Это" in result, (
            f"Первая часть абзаца не переведена. Результат: {result}"
        )
        assert "жирный" in result, f"Содержимое bold не переведено. Результат: {result}"
        assert "Перейдите" in result, (
            f"Вторая часть абзаца не переведена. Результат: {result}"
        )

    def test_definition_list_breaks_previous_structure(self, mock_translator):
        """Баг: Список определений ломает предыдущую структуру (вкладывается в список).

        Сценарий из большого теста:
        После списков идёт definition list, но термин оказывается внутри
        предыдущего вложенного списка вместо того чтобы быть на отдельном уровне.
        """
        source_markdown = (
            "- Item 1\n    - Nested Item 1.1\n\nTerm text\n: Definition text"
        )

        translation_dict = {
            "Item 1": "Элемент 1",
            "Nested Item 1.1": "Вложенный элемент 1.1",
            "Term text": "Текст термина",
            "Definition text": "Текст определения",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Термин не должен быть внутри вложенного списка (не должно быть 4+ пробелов перед ним)
        lines = result.split("\n")
        term_line_idx = None
        for i, line in enumerate(lines):
            if "Текст термина" in line or "Term text" in line:
                term_line_idx = i
                break

        if term_line_idx is not None:
            term_line = lines[term_line_idx]
            # Проверяем что термин не имеет отступа как у вложенного списка
            stripped = term_line.lstrip()
            indent = len(term_line) - len(stripped)
            assert indent < 4, (
                f"Термин имеет неправильный отступ ({indent} пробелов). "
                f"Он оказался внутри вложенного списка. Результат: {result}"
            )

    def test_code_blockquote_multiple_fences(self, mock_translator):
        """Баг: Код в цитате генерирует множественные fence блоки.

        Сценарий из большого теста показывает катастрофическое разрушение:
        ```
                > ```
        ```

            > def hello():
                >  print('world')
                > ```

        Вместо ожидаемого:
        > ```python
        > def hello():
        >     print('world')
        > ```
        """
        source_markdown = "> ```python\n> def hello():\n>     print('world')\n> ```"

        translation_dict = {}

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Подсчитываем количество fence блоков
        fence_count = result.count("```")
        assert fence_count == 2, (
            f"Ожидалось ровно 2 fence (открывающий и закрывающий), "
            f"найдено {fence_count}. Это указывает на разрушение структуры. "
            f"Результат:\n{result}"
        )

        # Проверяем что код находится между fence
        lines = result.split("\n")
        in_code_block = False
        code_content_lines = []

        for line in lines:
            if "```" in line:
                in_code_block = not in_code_block
            elif in_code_block:
                code_content_lines.append(line)

        assert len(code_content_lines) >= 2, (
            f"Содержимое кода потеряно. Найдено строк: {len(code_content_lines)}. "
            f"Результат: {result}"
        )

    def test_table_cells_not_translated(self, mock_translator):
        """Баг: Ячейки таблицы не переводятся.

        Сценарий из большого теста:
        Input:  | Name | Age |
        Expected: | Имя | Возраст |
        Actual:   | Name | Age |  (остаётся на английском)
        """
        source_markdown = "| Name | Age |\n|------|-----|\n| John | 30  |"

        translation_dict = {
            "Name": "Имя",
            "Age": "Возраст",
            "John": "Джон",
            "30": "30",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        # Проверяем перевод каждой ячейки
        assert "Имя" in result, f"Ячейка 'Name' не переведена. Результат: {result}"
        assert "Возраст" in result, f"Ячейка 'Age' не переведена. Результат: {result}"
        assert "Джон" in result, f"Ячейка 'John' не переведена. Результат: {result}"

    def test_task_list_items_not_translated(self, mock_translator):
        """Баг: Элементы task list не переводятся.

        Сценарий из большого теста:
        Input:  - [x] Done task
        Expected: - [x] Выполненная задача
        Actual:   - [x] Done task  (остаётся на английском)
        """
        source_markdown = "- [x] Done task\n- [ ] Pending task"

        # html_inline используется для checkbox, т.к. парсер создаёт html_inline токен
        translation_dict = {
            "{html_1}Done task": "{html_1}Выполнена",
            "{html_1}Pending task": "{html_1}В ожидании",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "Выполнена" in result, (
            f"Задача 'Done task' не переведена. Результат: {result}"
        )
        assert "В ожидании" in result, (
            f"Задача 'Pending task' не переведена. Результат: {result}"
        )

    def test_final_paragraph_not_translated(self, mock_translator):
        """Баг: Финальный абзац документа не переводится.

        Сценарий из большого теста:
        Input:  Some text after.
        Expected: Некоторый текст после.
        Actual:   Some text after.  (остаётся на английском)
        """
        # Тестируем в контексте всего документа
        source_markdown = "---\ntitle: Document\n---\n\n## Title\n\nSome text after."

        translation_dict = {
            "Title": "Заголовок",
            "Some text after.": "Некоторый текст после.",
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "Некоторый текст после." in result, (
            f"Финальный абзац не переведён. Результат: {result}"
        )
