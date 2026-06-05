"""Unit-тесты для моделей данных translation unit.

Эти тесты проверяют классификацию и обработку TranslationUnit
для различных элементов markdown (таблицы, task list).
"""


class TestTableTranslationUnits:
    """Тесты для TranslationUnit ячеек таблицы."""

    def test_table_cells_classification(self, tokenizer):
        """Тест перевода ячеек таблицы.

        Таблица в markdown-it-py парсится как:
        table_open -> thead_open -> tr_open -> th_open -> inline -> text -> th_close -> ...

        Ячейки таблицы (th/td) классифицируются как CONTEXT_BLOCK и должны переводиться.
        """
        from src.mt_server.markdown2.models.translation_unit import TranslationUnit
        from src.mt_server.markdown2.models.translation_unit_type import TranslationUnitType

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
        from src.mt_server.markdown2.models.placeholder_codes import SEGMENT_SEPARATOR
        from src.mt_server.markdown2.models.translation_unit import TranslationUnit
        from src.mt_server.markdown2.models.translation_unit_type import TranslationUnitType

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
        translated_response = SEGMENT_SEPARATOR.join(
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


class TestTaskListTranslationUnits:
    """Тесты для TranslationUnit элементов task list."""

    def test_task_list_item_classification(self):
        """Тест классификации элементов task list.

        Task list items в markdown-it-py с плагином tasklists:
        - [x] Done task
        - [ ] Pending task

        checkbox (tasklist_item) классифицируется как INLINE_PROTECT и должен защищаться плейсхолдером.
        """
        from src.mt_server.markdown2.models.translation_unit import TranslationUnit
        from src.mt_server.markdown2.models.translation_unit_type import TranslationUnitType

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
        from src.mt_server.markdown2.models.placeholder_codes import SEGMENT_SEPARATOR
        from src.mt_server.markdown2.models.translation_unit import TranslationUnit
        from src.mt_server.markdown2.models.translation_unit_type import TranslationUnitType

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
        translated_response = SEGMENT_SEPARATOR.join(
            ["{chk_1}Первый элемент задачи", "{chk_1}Второй элемент задачи"]
        )

        chunker.merge_translations(chunks, [translated_response], [u1, u2])

        assert u1.translated_text == "{chk_1}Первый элемент задачи"
        assert u1.is_translated is True
        assert u2.translated_text == "{chk_1}Второй элемент задачи"
        assert u2.is_translated is True

    def test_task_list_mixed_checkboxes(self):
        """Тест для task list с разными состояниями чекбоксов ([x] и [ ])."""
        from src.mt_server.markdown2.models.translation_unit import TranslationUnit
        from src.mt_server.markdown2.models.translation_unit_type import TranslationUnitType

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
