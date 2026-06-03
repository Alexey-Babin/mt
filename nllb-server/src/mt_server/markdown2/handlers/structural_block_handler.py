"""Модуль для обработки структурных блоков (списки, цитаты, блоки кода)."""

import logging
from typing import TYPE_CHECKING, Optional

from markdown_it.tree import SyntaxTreeNode

from ..node_type import get_unit_type
from ..translation_unit_type import TranslationUnitType
from ..unit_factory import UnitFactory

if TYPE_CHECKING:
    from ..ast_walker import ASTWalker

logger = logging.getLogger("uvicorn.error")


class StructuralBlockHandler:
    """Обрабатывает структурные блоки - списки, цитаты, блоки кода."""

    def __init__(self, walker: "ASTWalker"):
        self._walker = walker

    def handle_node(
        self,
        node: SyntaxTreeNode,
        parent_id: Optional[str],
        index: int,
    ) -> bool:
        """
        Обрабатывает узел как структурный блок.

        Returns:
            True если узел был обработан, False если это не структурный блок
        """
        unit_type = get_unit_type(node.type)

        if unit_type != TranslationUnitType.STRUCTURAL_IGNORE:
            return False

        # Особая обработка для inline-контейнера
        if node.type == "inline":
            for idx, child in enumerate(node.children or []):
                self._walker._collect_inline(child, parent_id, idx)
            return True

        self._handle_block(node, parent_id, index)
        return True

    def _handle_block(
        self,
        node: SyntaxTreeNode,
        parent_id: Optional[str],
        index: int,
    ):
        """Обрабатывает структурный блок любого типа."""
        is_base_type = not node.type.endswith("_open") and not node.type.endswith(
            "_close"
        )

        # Для одиночных токенов (fence, code_block с nesting=0) создаём пару open/close сразу
        if is_base_type and node.type in (
            "fence",
            "code_block",
            "math_block",
            "html_block",
        ):
            self._handle_open(node, parent_id, index)
            return

        if is_base_type:
            self._handle_open(node, parent_id, index)
        elif node.type.endswith("_close"):
            self._handle_close(node, parent_id, index)
        elif node.type.endswith("_open"):
            self._handle_open(node, parent_id, index)

    def _handle_open(
        self,
        node: SyntaxTreeNode,
        parent_id: Optional[str],
        index: int,
    ):
        """Создаёт открывающий маркер структурного блока и рекурсивно обрабатывает детей."""
        node_id = self._walker._generate_node_id()
        node_info = UnitFactory.extract_node_info(node)

        logger.debug(
            "Structural block open: type=%s, node_id=%s, level=%d",
            node.type,
            node_id,
            node.level,
        )

        unit = UnitFactory.create(
            node_id=node_id,
            node_type=node.type,
            unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
            original_text=node_info["content"],
            extracted_text=node_info["content"],
            need_translation=False,
            parent_id=parent_id,
            index_in_parent=index,
            level=node_info["level"],
            tag=node_info["tag"],
            attrs=node_info["attrs"],
            info=node_info["info"],
        )
        self._walker.units.append(unit)

        # Если это одиночный блок кода/математики/HTML - блокируем рекурсию
        if node.type in ("fence", "code_block", "math_block", "html_block"):
            close_node_id = self._walker._generate_node_id()
            close_unit = UnitFactory.create_close_marker(
                node_id=close_node_id,
                node_type=node.type
                + "_close",  # Добавляем суффикс _close для закрывающего маркера
                unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
                parent_id=parent_id,
                index_in_parent=index,
                level=node_info["level"],
                tag=node_info["tag"],
            )
            self._walker.units.append(close_unit)
            return

        # Для парных структурных блоков спускаемся к детям
        if node.children:
            for idx, child in enumerate(node.children):
                self._walker._traverse(child, parent_id=node_id, index=idx)

        # Создаём закрывающий маркер для всех парных структурных блоков,
        # которые SyntaxTreeNode представляет как один узел без суффиксов _open/_close.
        # Это blockquote, bullet_list, ordered_list, list_item, dl, table и её части.
        _PAIRED_STRUCTURAL_BLOCKS = {
            "table", "thead", "tbody", "tr",
            "blockquote",
            "bullet_list", "ordered_list", "list_item",
            "dl", "field_list", "field",
            "footnote_block",
        }
        if node.type in _PAIRED_STRUCTURAL_BLOCKS:
            close_node_id = self._walker._generate_node_id()
            close_unit = UnitFactory.create_close_marker(
                node_id=close_node_id,
                node_type=f"{node.type}_close",
                unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
                parent_id=parent_id,
                index_in_parent=index,
                level=node_info["level"],
                tag=node_info["tag"],
            )
            self._walker.units.append(close_unit)
            logger.debug(
                "Created close marker for structural block: %s_close", node.type
            )

    def _handle_close(
        self,
        node: SyntaxTreeNode,
        parent_id: Optional[str],
        index: int,
    ):
        """Создаёт закрывающий маркер структурного блока."""
        node_id = self._walker._generate_node_id()

        logger.debug(
            "Structural block close: type=%s, node_id=%s",
            node.type,
            node_id,
        )

        unit = UnitFactory.create_close_marker(
            node_id=node_id,
            node_type=node.type,
            unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
            parent_id=parent_id,
            index_in_parent=index,
            level=node.level,
            tag=node.tag,
        )
        self._walker.units.append(unit)
