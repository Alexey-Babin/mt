"""Известные баги markdown переводчика.

Эти тесты фиксируют конкретные проблемы, которые были выявлены
в процессе разработки и должны оставаться зелёными.
"""


class TestKnownBugs:
    """Тесты известных багов."""

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
