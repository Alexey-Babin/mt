"""Модуль управления состоянием и стеком блоков.

Отвечает за:
- Управление стеком вложенности блоков (цитаты, списки, определения)
- Вычисление префиксов для строк на основе текущего состояния стека
- Обработку структурных маркеров (открытие/закрытие блоков)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..translation_unit import TranslationUnit

logger = logging.getLogger("uvicorn.error")


class StateMachine:
    """Управляет стеком блоков и вычисляет префиксы для вложенности."""

    def __init__(self):
        self._block_stack: List[Dict[str, Any]] = []

    def reset(self):
        """Сбрасывает состояние машины."""
        self._block_stack = []

    @property
    def block_stack(self) -> List[Dict[str, Any]]:
        """Возвращает текущий стек блоков."""
        return self._block_stack

    @property
    def stack_size(self) -> int:
        """Возвращает размер стека."""
        return len(self._block_stack)

    def push_block(
        self,
        block_type: str,
        marker: str = "",
        is_first_paragraph: bool = False,
        is_first_line: bool = False,
    ):
        """Пушит блок в стек с метаданными."""
        block_data: Dict[str, Any] = {
            "type": block_type,
            "marker": marker,
        }
        if is_first_paragraph:
            block_data["is_first_paragraph"] = True
        if is_first_line:
            block_data["is_first_line"] = True

        self._block_stack.append(block_data)
        logger.debug(
            "Pushed block to stack: type=%s, stack_size=%d",
            block_type,
            len(self._block_stack),
        )

    def pop_block(self, expected_type: str) -> bool:
        """Безопасно снимает блок со стека, если тип совпадает."""
        if self._block_stack and self._block_stack[-1]["type"] == expected_type:
            self._block_stack.pop()
            logger.debug(
                "Popped block from stack: type=%s, stack_size=%d",
                expected_type,
                len(self._block_stack),
            )
            return True
        return False

    def get_current_prefix(self, for_block_start: bool = False) -> Tuple[str, str]:
        """Вычисляет префикс для текущей строки на основе стека вложенности.

        Возвращает кортеж (line_prefix, item_marker):
        - line_prefix: префикс для продолжения строки (отступы списков, цитаты)
        - item_marker: маркер элемента списка (только для первой строки)

        Расширен поддержкой списков определений (dt/dd).
        """
        line_prefix = ""
        item_marker = ""
        list_level = 0

        for block in self._block_stack:
            b_type = block["type"]

            if b_type == "blockquote":
                line_prefix += "> "

            elif b_type in ("bullet_list", "ordered_list"):
                if list_level > 0:
                    line_prefix += "    "
                list_level += 1

            elif b_type == "list_item":
                if for_block_start and block.get("is_first_paragraph", False):
                    item_marker = f"{block['marker']} "
                    block["is_first_paragraph"] = False
                elif not for_block_start:
                    line_prefix += " " * (len(block["marker"]) + 1)

            # Поддержка списков определений
            elif b_type == "dd":
                if for_block_start and block.get("is_first_line", False):
                    item_marker = ": "
                    block["is_first_line"] = False
                elif not for_block_start:
                    # Последующие строки блока dd получают отступ в 2 пробела
                    line_prefix += "  "

        return line_prefix, item_marker

    def is_inside_list(self) -> bool:
        """Проверяет, находимся ли мы внутри списка."""
        return any(
            block["type"] in ("bullet_list", "ordered_list", "list_item")
            for block in self._block_stack
        )

    def is_inside_blockquote(self) -> bool:
        """Проверяет, находимся ли мы внутри цитаты."""
        return any(block["type"] == "blockquote" for block in self._block_stack)

    def get_parent_list_marker(self) -> Optional[str]:
        """Получает маркер родительского списка для элемента списка."""
        parent_list = next(
            (
                b
                for b in reversed(self._block_stack)
                if b["type"] in ("bullet_list", "ordered_list")
            ),
            None,
        )
        return parent_list["marker"] if parent_list else None

    def handle_structural_open(
        self, base_type: str, unit: TranslationUnit
    ) -> Optional[Dict[str, Any]]:
        """Обрабатывает открытие структурного блока.

        Возвращает данные для пуша в стек или None, если обработка не требуется.
        """
        marker = "-"

        if base_type == "ordered_list":
            start_num = unit.attrs.get("start", 1) if unit.attrs else 1
            marker = f"{start_num}."
            logger.debug("Opening ordered list: start=%d", start_num)

        elif base_type == "bullet_list":
            if unit.info and unit.info in ("-", "*", "+"):
                marker = unit.info
            elif unit.tag and unit.tag in ("-", "*", "+"):
                marker = unit.tag
            logger.debug("Opening bullet list: marker=%s", marker)

        elif base_type == "list_item":
            # Элемент списка наследует маркер от своего родительского контейнера
            parent_marker = self.get_parent_list_marker()
            if parent_marker:
                marker = parent_marker
            logger.debug("Opening list item: marker=%s", marker)

        return {
            "type": base_type,
            "marker": marker,
            "is_first_paragraph": base_type == "list_item",
        }
