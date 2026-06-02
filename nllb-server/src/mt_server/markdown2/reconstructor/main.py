"""Рефакторированный MarkdownReconstructor с декомпозицией логики.

Этот модуль представляет собой главный класс сборки Markdown-документа,
который делегирует специализированные задачи отдельным компонентам:
- StateMachine: управление стеком блоков и префиксами
- BlockWriter: запись текста с правильными отступами
- PlaceholderRestorer: восстановление плейсхолдеров
- TableHandler: обработка таблиц
- CodeBlockHandler: обработка блоков кода
"""

import logging
from typing import Dict, List

from src.mt_server.config import settings

from ..translation_unit import TranslationUnit
from ..translation_unit_type import TranslationUnitType
from .block_writer import BlockWriter
from .code_block_handler import CodeBlockHandler
from .placeholder_restorer import PlaceholderRestorer
from .state_machine import StateMachine
from .table_handler import TableHandler

logger = logging.getLogger("uvicorn.error")


class MarkdownReconstructor:
    """Конечный автомат (State Machine) для обратной сборки Markdown-документа.

    Линейно обходит плоский список TranslationUnit, восстанавливает структуру
    вложенности (через стек блоков) и разворачивает плейсхолдеры в инлайнах.
    """

    def __init__(self):
        # Компоненты делегирования
        self._state_machine = StateMachine()
        self._writer = BlockWriter(self._state_machine.get_current_prefix)
        self._placeholder_restorer = PlaceholderRestorer()
        self._table_handler = TableHandler(self._writer, self._state_machine)
        self._code_block_handler = CodeBlockHandler(self._writer, self._state_machine)

    def reconstruct(self, units: List[TranslationUnit]) -> str:
        """Главный метод сборщика.

        Принимает плоский упорядоченный список юнитов и возвращает монолитную
        строку готового отформатированного Markdown-документа.
        """
        self._reset_state()

        logger.debug("Reconstruction start: total_units=%d", len(units))

        if settings.debug_mode:
            self._log_unit_distribution(units)

        for unit in units:
            self._process_unit(unit)

        result = self._writer.get_buffer_content()
        logger.info("Reconstruction complete: output_length=%d characters", len(result))
        return result

    def _reset_state(self):
        """Сбрасывает состояние всех компонентов."""
        self._state_machine.reset()
        self._writer.reset()
        self._placeholder_restorer.reset()

    def _log_unit_distribution(self, units: List[TranslationUnit]):
        """Логирует распределение типов юнитов (для отладки)."""
        unit_type_counts: Dict[str, int] = {}
        for unit in units:
            unit_type_counts[unit.unit_type.value] = (
                unit_type_counts.get(unit.unit_type.value, 0) + 1
            )
        logger.debug("Unit type distribution: %s", unit_type_counts)

    def _process_unit(self, unit: TranslationUnit):
        """Обрабатывает один юнит в зависимости от его типа."""
        if unit.unit_type == TranslationUnitType.STRUCTURAL_IGNORE:
            self._handle_structural_marker(unit)

        elif unit.unit_type == TranslationUnitType.CONTEXT_BLOCK:
            self._handle_context_block(unit)

        elif unit.unit_type == TranslationUnitType.SPECIAL_CASE:
            self._handle_special_case(unit)

    def _handle_structural_marker(self, unit: TranslationUnit):
        """Обрабатывает маркеры каркаса документа (цитаты, списки, таблицы, fence)."""
        is_open = unit.node_type.endswith("_open")
        is_close = unit.node_type.endswith("_close")
        base_type = unit.node_type.replace("_open", "").replace("_close", "")

        logger.debug(
            "Structural marker: type=%s, is_open=%s, is_close=%s",
            unit.node_type,
            is_open,
            is_close,
        )

        # === ТАБЛИЦЫ: специальная обработка ===
        if self._handle_table_structure(base_type, is_open, is_close, unit):
            return

        # Хронологический перехват блоков кода (fence, code_block) и разделителей (hr)
        if base_type in ("fence", "code_block"):
            # Обрабатываем если: это открывающий маркер ИЛИ это базовый тип без суффиксов
            if is_open or (not is_open and not is_close):
                self._code_block_handler.handle_fence(unit)
            return  # Игнорируем fence_close и повторные обработки базовых типов

        if unit.node_type == "hr":
            self._code_block_handler.handle_hr()
            return

        # --- ОБРАБОТКА ЗАКРЫВАЮЩИХ МАРКЕРОВ ---
        if is_close:
            self._handle_structural_close(base_type)
            return

        # --- СТАНДАРТНАЯ СТРУКТУРНАЯ ЛОГИКА ДЛЯ ПАРНЫХ КОНТЕЙНЕРОВ ---
        # Особая обработка для blockquote без суффиксов
        if base_type == "blockquote" and not is_open and not is_close:
            self._state_machine.push_block(
                base_type,
                marker="",
                is_first_paragraph=False,
            )
            return

        # Обработка базовых типов без суффиксов как открывающих тегов
        if not is_open and not is_close:
            is_open = True

        if is_open:
            self._handle_structural_open(base_type, unit)

        elif is_close:
            self._handle_structural_close(base_type)

    def _handle_table_structure(
        self, base_type: str, is_open: bool, is_close: bool, unit: TranslationUnit
    ) -> bool:
        """Обрабатывает табличную структуру.

        Возвращает True, если это была таблица и обработка завершена.
        """
        if base_type in ("table", "thead"):
            # Для таблиц мы не используем стек, а просто пропускаем эти узлы
            # Разделители | добавляются при обработке th/td ячеек
            return True

        if base_type == "tbody":
            if not is_close:
                self._table_handler.handle_tbody_open()
            else:
                self._table_handler.handle_tbody_close()
            return True

        if base_type == "tr":
            if not is_close:
                self._table_handler.handle_tr_open()
            else:
                self._table_handler.handle_tr_close()
            return True

        if base_type in ("th", "td"):
            if is_close:
                self._table_handler.handle_cell_close(base_type)
            else:
                self._table_handler.handle_cell_open(unit)
            return True

        return False

    def _handle_structural_open(self, base_type: str, unit: TranslationUnit):
        """Обрабатывает открытие структурного блока."""
        # Если новый блок имеет level=0 (корневой уровень), закрываем все открытые списки
        if unit.level == 0 and base_type in ("dl", "bullet_list", "ordered_list"):
            self._close_all_lists()
        block_data = self._state_machine.handle_structural_open(base_type, unit)
        if block_data:
            self._state_machine.push_block(
                block_data["type"],
                marker=block_data["marker"],
                is_first_paragraph=block_data.get("is_first_paragraph", False),
            )

    def _close_all_lists(self):
        """Закрывает все открытые блоки списков до достижения корневого уровня."""
        while self._state_machine.stack_size > 0:
            top = self._state_machine.block_stack[-1]
            if top["type"] in ("bullet_list", "ordered_list", "list_item"):
                self._state_machine.pop_block(top["type"])
            else:
                break

    def _handle_structural_close(self, base_type: str):
        """Обрабатывает закрытие структурного блока."""
        self._state_machine.pop_block(base_type)

        # Добавляем перенос строки после закрытия контейнеров
        if base_type in (
            "blockquote",
            "bullet_list",
            "ordered_list",
            "table",
            "dl",
        ):
            self._writer.ensure_newline()

    def _handle_special_case(self, unit: TranslationUnit):
        """Обрабатывает узлы метаданных Front Matter.

        Восстанавливает технический блок метаданных в начале документа,
        оборачивая его контент в стандартные ограничители '---'.
        """
        if unit.node_type == "front_matter":
            logger.debug("Handling front matter special case")
            # Извлекаем текст метаданных
            fm_content = (
                unit.translated_text if unit.translated_text else unit.original_text
            )

            # Убеждаемся, что контент заканчивается на перевод строки
            if fm_content and not fm_content.endswith("\n"):
                fm_content += "\n"

            # Формируем валидный блок Front Matter
            # Метаданные всегда находятся на самом верхнем уровне документа
            front_matter_block = f"---\n{fm_content}---\n\n"
            front_matter_block = f"---\n{fm_content}---\n"
            self._writer.write_raw(front_matter_block)
            logger.debug(
                "Front matter block written: length=%d characters",
                len(front_matter_block),
            )

    def _handle_context_block(self, unit: TranslationUnit):
        """Обрабатывает текстовые контейнеры (включая dt и dd)."""
        is_close = unit.node_type.endswith("_close")
        base_type = unit.node_type.replace("_open", "").replace("_close", "")

        # === ТАБЛИЦЫ: специальная обработка tbody ===
        if base_type == "tbody":
            if not is_close:
                self._table_handler.handle_tbody_open()
            else:
                self._table_handler.handle_tbody_close()
            return

        if is_close:
            self._handle_context_block_close(base_type)
            return

        # Узлы dt и dd сами являются открывающими контекстными блоками
        if base_type in ("dt", "dd"):
            self._state_machine.push_block(
                base_type,
                marker="",
                is_first_line=True,
            )

        # Получаем текст для восстановления
        text_to_restore = (
            unit.translated_text
            if unit.translated_text is not None
            else unit.extracted_text
        )

        logger.debug(
            "Restoring inline placeholders for %s: text_length=%d, placeholders_count=%d",
            base_type,
            len(text_to_restore),
            len(unit.placeholders) if unit.placeholders else 0,
        )
        restored_markdown = self._placeholder_restorer.restore(text_to_restore, unit)

        # Форматируем заголовок
        if unit.node_type == "heading":
            level = unit.level if unit.level else 1
            block_content = "#" * level + " " + restored_markdown
            logger.debug(
                "Heading level %d: content_length=%d", level, len(block_content)
            )
        else:
            block_content = restored_markdown

        # Для ячеек таблицы не используем префиксы
        if base_type in ("th", "td"):
            self._writer.write_raw(block_content)
        else:
            self._writer.write_with_prefix(block_content)

    def _handle_context_block_close(self, base_type: str):
        """Обрабатывает закрытие контекстного блока."""
        logger.debug("Context block close: type=%s", base_type)

        # === ТАБЛИЦЫ: обработка закрытия ячеек ===
        if base_type in ("th", "td"):
            self._table_handler.handle_cell_close(base_type)
            return

        # Снимаем контекстный блок dt/dd со стека
        if self._state_machine.pop_block(base_type):
            pass  # Логирование уже есть в pop_block

        # Добавляем переносы строк после определенных типов блоков
        if base_type in (
            "paragraph",
            "heading",
            "field_name",
            "field_body",
            "dt",
            "dd",
        ):
            # Для paragraph на верхнем уровне добавляем двойной перенос строки
            if base_type == "paragraph" and self._state_machine.stack_size == 0:
                self._writer.ensure_double_newline()
            else:
                self._writer.ensure_newline()

        # Убираем лишний перенос строки в конце файла (оставляем максимум один \n)
        buffer = self._writer.get_buffer_content()
        if buffer.endswith("\n\n\n"):
            self._writer._buffer = [buffer.rstrip("\n") + "\n"]
