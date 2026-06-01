"""Модуль для обработки контекстных блоков (абзацы, заголовки, ячейки таблиц)."""

import logging
from typing import TYPE_CHECKING, List, Optional, Tuple

from markdown_it.tree import SyntaxTreeNode

from ..node_type import get_unit_type
from ..placeholder import PlaceholderManager
from ..translation_unit import TranslationUnit
from ..translation_unit_type import TranslationUnitType
from ..unit_factory import UnitFactory

if TYPE_CHECKING:
    from ..ast_walker import ASTWalker

logger = logging.getLogger("uvicorn.error")


def _extract_heading_level(node: SyntaxTreeNode) -> int:
    """Извлекает уровень заголовка из тега (например, 'h2' -> 2).

    markdown-it-py не устанавливает node.level для заголовков,
    поэтому извлекаем уровень из тега (tag='h1', 'h2', ...).
    """
    import re

    HEADING_TAG_PATTERN = re.compile(r"^h([1-6])$")
    tag = node.tag or ""
    match = HEADING_TAG_PATTERN.match(tag)
    if match:
        return int(match.group(1))
    return 1  # fallback на h1 по умолчанию


class ContextBlockHandler:
    """Обрабатывает контекстные блоки - абзацы, заголовки, ячейки таблиц."""

    def __init__(self, walker: "ASTWalker"):
        self._walker = walker
        self._context_stack: List[Tuple[TranslationUnit, PlaceholderManager]] = []

    @property
    def has_active_context(self) -> bool:
        """Проверяет, есть ли активный контекст в стеке."""
        return bool(self._context_stack)

    @property
    def current_context(self) -> Tuple[TranslationUnit, PlaceholderManager]:
        """Возвращает текущий контекст из стека."""
        return self._context_stack[-1]

    def handle_node(
        self,
        node: SyntaxTreeNode,
        parent_id: Optional[str],
        index: int,
    ) -> bool:
        """
        Обрабатывает узел как контекстный блок.

        Returns:
            True если узел был обработан, False если это не контекстный блок
        """
        unit_type = get_unit_type(node.type)

        if unit_type != TranslationUnitType.CONTEXT_BLOCK:
            return False

        # Если есть активный контекст и это не новый открывающий блок - собираем инлайн
        if self._context_stack and not (
            unit_type == TranslationUnitType.CONTEXT_BLOCK
            and node.type.endswith("_open")
        ):
            self._walker._collect_inline(node, parent_id, index)
            return True

        # Обработка открывающего/базового блока
        if not node.type.endswith("_close"):
            self._handle_open(node, parent_id, index)
            return True

        # Обработка закрывающего блока
        self._handle_close(node, parent_id, index)
        return True

    def _handle_open(
        self,
        node: SyntaxTreeNode,
        parent_id: Optional[str],
        index: int,
    ):
        """Создаёт контекстный блок и пушит его в стек."""
        node_id = self._walker._generate_node_id()
        clean_type = node.type.replace("_open", "")

        logger.debug(
            "Context block open: type=%s, node_id=%s, level=%d",
            clean_type,
            node_id,
            node.level,
        )

        node_info = UnitFactory.extract_node_info(node)
        level = (
            _extract_heading_level(node)
            if clean_type == "heading"
            else node_info["level"]
        )

        context_unit = UnitFactory.create(
            node_id=node_id,
            node_type=clean_type,
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="",
            need_translation=True,
            parent_id=parent_id,
            index_in_parent=index,
            level=level,
            tag=node_info["tag"],
            attrs=node_info["attrs"],
        )

        manager = PlaceholderManager()

        # Добавляем юнит в список СРАЗУ, сохраняя DFS порядок
        self._walker.units.append(context_unit)
        self._context_stack.append((context_unit, manager))

        # Рекурсивно спускаемся к детям
        for idx, child in enumerate(node.children):
            self._walker._traverse(child, parent_id=node_id, index=idx)

        # Фиксируем плейсхолдеры после обработки всех дочерних элементов
        context_unit.placeholders = list(manager.registry.values())
        logger.debug(
            "Context block complete: type=%s, node_id=%s, placeholders_count=%d",
            clean_type,
            node_id,
            len(context_unit.placeholders),
        )

        # Для базовых типов блоков (без суффиксов) сразу создаём закрывающий маркер
        if not node.type.endswith("_open"):
            close_node_id = self._walker._generate_node_id()
            close_unit = UnitFactory.create_close_marker(
                node_id=close_node_id,
                node_type=f"{clean_type}_close",
                unit_type=TranslationUnitType.CONTEXT_BLOCK,
                parent_id=parent_id,
                index_in_parent=index,
                level=node_info["level"],
                tag=node_info["tag"],
            )
            self._walker.units.append(close_unit)
            self._context_stack.pop()

    def _handle_close(self, node: SyntaxTreeNode, parent_id: Optional[str], index: int):
        """Создаёт закрывающий маркер контекстного блока."""
        if not self._context_stack:
            return

        current_unit, current_manager = self._context_stack[-1]

        logger.debug(
            "Context block close: type=%s, node_id=%s, text_length=%d",
            current_unit.node_type,
            current_unit.node_id,
            len(current_unit.extracted_text),
        )

        # Фиксируем все собранные плейсхолдеры
        current_unit.placeholders = list(current_manager.registry.values())

        # Добавляем закрывающий пустой маркер-маяк
        node_id = self._walker._generate_node_id()
        close_unit = UnitFactory.create_close_marker(
            node_id=node_id,
            node_type=node.type,
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            parent_id=parent_id,
            index_in_parent=index,
            level=node.level,
            tag=node.tag,
        )
        self._walker.units.append(close_unit)

        # Удаляем закрытый контекст из стека
        self._context_stack.pop()
