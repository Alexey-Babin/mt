"""Модуль для обработки специальных случаев (Front Matter и другие исключения)."""

import logging
from typing import TYPE_CHECKING, Optional

from markdown_it.tree import SyntaxTreeNode

from ...models.node_type import get_unit_type
from ...models.translation_unit_type import TranslationUnitType
from ...models.unit_factory import UnitFactory

if TYPE_CHECKING:
    from ..walker import ASTWalker

logger = logging.getLogger("uvicorn.error")


class SpecialCaseHandler:
    """Обрабатывает специальные случаи - Front Matter и другие исключения."""

    def __init__(self, walker: "ASTWalker"):
        self._walker = walker

    def handle_node(
        self,
        node: SyntaxTreeNode,
        parent_id: Optional[str],
        index: int,
    ) -> bool:
        """
        Обрабатывает узел как специальный случай.

        Returns:
            True если узел был обработан, False если это не специальный случай
        """
        unit_type = get_unit_type(node.type)

        if unit_type != TranslationUnitType.SPECIAL_CASE:
            return False

        self._handle_special_case(node, parent_id, index)
        return True

    def _handle_special_case(
        self,
        node: SyntaxTreeNode,
        parent_id: Optional[str],
        index: int,
    ):
        """Обрабатывает Front Matter метаданные."""
        node_id = self._walker._generate_node_id()

        logger.debug("Special case: type=%s, node_id=%s", node.type, node_id)

        node_info = UnitFactory.extract_node_info(node)

        special_unit = UnitFactory.create(
            node_id=node_id,
            node_type=node.type,
            unit_type=TranslationUnitType.SPECIAL_CASE,
            original_text=node_info["content"],
            extracted_text=node_info["content"],
            need_translation=False,
            parent_id=parent_id,
            index_in_parent=index,
            level=node_info["level"],
            tag=node_info["tag"],
        )
        self._walker.units.append(special_unit)
