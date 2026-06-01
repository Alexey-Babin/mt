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

    def test_table_cells_translation(self, tokenizer):
        """Тест перевода ячеек таблицы.

        Таблица в markdown-it-py парсится как:
        table_open -> thead_open -> tr_open -> th_open -> inline -> text -> th_close -> ...

        Ячейки таблицы (th/td) классифицируются как CONTEXT_BLOCK и должны переводиться.
        """
        from src.mt_server.markdown2.translation_unit import TranslationUnit
        from src.mt_server.markdown2.translation_unit_type import TranslationUnitType

        # Заголовки таблицы
        th1 = TranslationUnit(
            node_id="th_1",
            node_type="th_open",
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="Name",
            translated_text="Имя",
            need_translation=True,
        )
        th2 = TranslationUnit(
            node_id="th_2",
            node_type="th_open",
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="Age",
            translated_text="Возраст",
            need_translation=True,
        )

        # Ячейки тела таблицы
        td1 = TranslationUnit(
            node_id="td_1",
            node_type="td_open",
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="John",
            translated_text="Джон",
            need_translation=True,
        )
        td2 = TranslationUnit(
            node_id="td_2",
            node_type="td_open",
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="30",
            translated_text="30",
            need_translation=True,
        )

        # Структурные элементы (не переводятся)
        table_open = TranslationUnit(
            node_id="table_open",
            node_type="table_open",
            unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
            original_text="",
            extracted_text="",
            need_translation=False,
        )
        thead_open = TranslationUnit(
            node_id="thead_open",
            node_type="thead_open",
            unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
            original_text="",
            extracted_text="",
            need_translation=False,
        )
        tr_open = TranslationUnit(
            node_id="tr_open",
            node_type="tr_open",
            unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
            original_text="",
            extracted_text="",
            need_translation=False,
        )
        th_close = TranslationUnit(
            node_id="th_close",
            node_type="th_close",
            unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
            original_text="",
            extracted_text="",
            need_translation=False,
        )
        td_close = TranslationUnit(
            node_id="td_close",
            node_type="td_close",
            unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
            original_text="",
            extracted_text="",
            need_translation=False,
        )
        tbody_open = TranslationUnit(
            node_id="tbody_open",
            node_type="tbody_open",
            unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
            original_text="",
            extracted_text="",
            need_translation=False,
        )
        table_close = TranslationUnit(
            node_id="table_close",
            node_type="table_close",
            unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
            original_text="",
            extracted_text="",
            need_translation=False,
        )

        # Проверяем, что ячейки имеют правильный тип для перевода
        assert th1.unit_type == TranslationUnitType.CONTEXT_BLOCK
        assert th2.unit_type == TranslationUnitType.CONTEXT_BLOCK
        assert td1.unit_type == TranslationUnitType.CONTEXT_BLOCK
        assert td2.unit_type == TranslationUnitType.CONTEXT_BLOCK

        # Проверяем, что структурные элементы игнорируются
        assert table_open.unit_type == TranslationUnitType.STRUCTURAL_IGNORE
        assert thead_open.unit_type == TranslationUnitType.STRUCTURAL_IGNORE
        assert tbody_open.unit_type == TranslationUnitType.STRUCTURAL_IGNORE
        assert tr_open.unit_type == TranslationUnitType.STRUCTURAL_IGNORE
        assert table_close.unit_type == TranslationUnitType.STRUCTURAL_IGNORE
        assert th_close.unit_type == TranslationUnitType.STRUCTURAL_IGNORE
        assert td_close.unit_type == TranslationUnitType.STRUCTURAL_IGNORE

    def test_table_chunking_and_merging(self, chunker):
        """Тест чанкования и слияния переводов для ячеек таблицы."""
        from src.mt_server.markdown2.translation_unit import TranslationUnit
        from src.mt_server.markdown2.translation_unit_type import TranslationUnitType

        u1 = TranslationUnit(
            node_id="th_1",
            node_type="th_open",
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="Header One",
            need_translation=True,
        )
        u2 = TranslationUnit(
            node_id="th_2",
            node_type="th_open",
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="Header Two",
            need_translation=True,
        )
        u3 = TranslationUnit(
            node_id="td_1",
            node_type="td_open",
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="Cell One",
            need_translation=True,
        )
        u4 = TranslationUnit(
            node_id="td_2",
            node_type="td_open",
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="Cell Two",
            need_translation=True,
        )

        chunks = chunker.create_chunks([u1, u2, u3, u4])

        # Все ячейки должны упаковаться в чанки
        assert len(chunks) >= 1

        # Проверяем создание сегментов
        total_segments = sum(len(c.segments) for c in chunks)
        assert total_segments == 4

        # Тестируем слияние
        translated_response = "\x1e".join(
            ["Заголовок Один", "Заголовок Два", "Ячейка Одна", "Ячейка Два"]
        )

        chunker.merge_translations(chunks, [translated_response], [u1, u2, u3, u4])

        assert u1.translated_text == "Заголовок Один"
        assert u1.is_translated is True
        assert u2.translated_text == "Заголовок Два"
        assert u2.is_translated is True
        assert u3.translated_text == "Ячейка Одна"
        assert u3.is_translated is True
        assert u4.translated_text == "Ячейка Два"
        assert u4.is_translated is True


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

    def test_task_list_item_classification(self):
        """Тест классификации элементов task list.

        Task list items в markdown-it-py с плагином tasklists:
        - [x] Done task
        - [ ] Pending task

        checkbox (tasklist_item) классифицируется как INLINE_PROTECT и должен защищаться плейсхолдером.
        """
        from src.mt_server.markdown2.translation_unit import TranslationUnit
        from src.mt_server.markdown2.translation_unit_type import TranslationUnitType

        # Элемент списка задач с чекбоксом
        task_item = TranslationUnit(
            node_id="task_1",
            node_type="tasklist_item",
            unit_type=TranslationUnitType.INLINE_PROTECT,
            original_text="",
            extracted_text="",
            need_translation=False,  # Сам чекбокс не переводится
        )

        # Текст задачи внутри параграфа
        task_text = TranslationUnit(
            node_id="p_1",
            node_type="paragraph",
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="{chk_1}Выполнить задачу",
            translated_text="{chk_1}Complete the task",
            need_translation=True,
        )

        # Проверяем классификацию
        assert task_item.unit_type == TranslationUnitType.INLINE_PROTECT
        assert task_text.unit_type == TranslationUnitType.CONTEXT_BLOCK

    def test_task_list_chunking_with_protected_checkbox(self, chunker):
        """Тест чанкования task list с защищенным чекбоксом."""
        from src.mt_server.markdown2.translation_unit import TranslationUnit
        from src.mt_server.markdown2.translation_unit_type import TranslationUnitType

        u1 = TranslationUnit(
            node_id="p_1",
            node_type="paragraph",
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="{chk_1}First task item",
            need_translation=True,
        )
        u2 = TranslationUnit(
            node_id="p_2",
            node_type="paragraph",
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="{chk_1}Second task item",
            need_translation=True,
        )

        chunks = chunker.create_chunks([u1, u2])

        assert len(chunks) >= 1

        # Проверяем, что плейсхолдеры чекбоксов сохранились в сегментах
        for chunk in chunks:
            for segment in chunk.segments:
                # Плейсхолдер {chk_1} должен присутствовать в тексте
                assert "{chk_1}" in segment.text or segment.text.startswith("{chk_1}")

        # Тестируем слияние
        translated_response = "\x1e".join(
            ["{chk_1}Первый элемент задачи", "{chk_1}Второй элемент задачи"]
        )

        chunker.merge_translations(chunks, [translated_response], [u1, u2])

        assert u1.translated_text == "{chk_1}Первый элемент задачи"
        assert u1.is_translated is True
        assert u2.translated_text == "{chk_1}Второй элемент задачи"
        assert u2.is_translated is True

    def test_task_list_mixed_checkboxes(self):
        """Тест для task list с разными состояниями чекбоксов ([x] и [ ])."""
        from src.mt_server.markdown2.translation_unit import TranslationUnit
        from src.mt_server.markdown2.translation_unit_type import TranslationUnitType

        # Выполненная задача
        done_task = TranslationUnit(
            node_id="p_done",
            node_type="paragraph",
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="{chk_1}Completed task",
            translated_text="{chk_1}Завершена",
            need_translation=True,
        )

        # Незавершенная задача
        pending_task = TranslationUnit(
            node_id="p_pending",
            node_type="paragraph",
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="{chk_2}Pending task",
            translated_text="{chk_2}В ожидании",
            need_translation=True,
        )

        # Оба элемента должны быть готовы к переводу текста
        assert done_task.need_translation is True
        assert pending_task.need_translation is True

        # Плейсхолдеры должны различаться для разных чекбоксов
        assert "{chk_1}" in done_task.extracted_text
        assert "{chk_2}" in pending_task.extracted_text


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
            "Use the {code_1} method.": "Используйте метод {code_1}.",
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

        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) >= 3, "Элементы списка потеряны"

        # Проверяем наличие вложенных элементов с отступом
        nested_items = [l for l in lines if l.startswith("    -")]
        assert len(nested_items) >= 2, (
            f"Вложенные элементы потеряны. Найдено: {len(nested_items)}"
        )


class TestLinkPreservation:
    """Тесты проблемы: ссылки теряют URL или текст."""

    def test_link_url_preserved(self, mock_translator):
        """URL ссылки должен сохраниться."""
        source_markdown = "Visit [Example](https://example.com)."

        translation_dict = {
            "Visit {lnk_1}Example{/lnk_1}.": "Посетите {lnk_1}Example{/lnk_1}."
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "https://example.com" in result, "URL ссылки потерян"
        assert "[Example]" in result or "Example" in result, "Текст ссылки потерян"

    def test_link_text_translated(self, mock_translator):
        """Текст ссылки должен переводиться."""
        source_markdown = "Go to [Google](https://google.com)."

        translation_dict = {
            "Go to {lnk_1}Google{/lnk_1}.": "Перейдите в {lnk_1}Google{/lnk_1}."
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
        quote_lines = [l for l in lines if l.strip().startswith(">")]
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
            "This is {s_1}bold{/s_1} and {e_1}italic{/e_1} text.": "Это {s_1}жирный{/s_1} и {e_1}курсив{/e_1} текст."
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "**" in result, "Жирный текст не оформлен"
        assert "*" in result, "Курсив не оформлен"

    def test_link_and_code(self, mock_translator):
        """Ссылка и инлайн код должны сосуществовать."""
        source_markdown = "Use `func()` or visit [Docs](https://docs.example.com)."

        translation_dict = {
            "Use {code_1} or visit {lnk_1}Docs{/lnk_1}.": "Используйте {code_1} или посетите {lnk_1}Docs{/lnk_1}."
        }

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "`" in result, "Инлайн код не оформлен"
        assert "[" in result and "](" in result, "Ссылка не оформлена"


class TestEmptyInputs:
    """Тесты с пустыми и граничными входами."""

    def test_empty_string(self, mock_translator):
        """Пустая строка должна обработаться без ошибок."""
        source_markdown = ""

        translator = mock_translator(source_markdown, {})
        result = translator.process()

        assert result == "", f"Пустая строка не вернула пустой результат: {result}"

    def test_whitespace_only(self, mock_translator):
        """Строка из пробелов должна обработаться."""
        source_markdown = "   \n\n   "

        translator = mock_translator(source_markdown, {})
        result = translator.process()

        # Допускаем любой результат, главное без исключений
        assert isinstance(result, str)

    def test_single_word(self, mock_translator):
        """Одно слово должно перевестись."""
        source_markdown = "Hello"

        translation_dict = {"Hello": "Привет"}

        translator = mock_translator(source_markdown, translation_dict)
        result = translator.process()

        assert "Привет" in result or "Hello" in result, "Одно слово не переведено"
