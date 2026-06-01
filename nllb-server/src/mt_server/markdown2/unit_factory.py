"""Фабрика для создания TranslationUnit объектов."""

from typing import Any, Dict, List, Optional

from markdown_it.tree import SyntaxTreeNode

from .placeholder import Placeholder
from .translation_unit import TranslationUnit
from .translation_unit_type import TranslationUnitType


class UnitFactory:
    """Фабрика для создания единиц перевода с общими параметрами."""

    @staticmethod
    def create(
        node_id: str,
        node_type: str,
        unit_type: TranslationUnitType,
        original_text: str = "",
        extracted_text: str = "",
        need_translation: bool = True,
        parent_id: Optional[str] = None,
        index_in_parent: int = 0,
        level: int = 0,
        tag: Optional[str] = None,
        attrs: Optional[Dict[str, Any]] = None,
        info: Optional[str] = None,
        placeholders: Optional[List[Placeholder]] = None,
    ) -> TranslationUnit:
        """Создаёт TranslationUnit с стандартными параметрами."""
        return TranslationUnit(
            node_id=node_id,
            node_type=node_type,
            unit_type=unit_type,
            original_text=original_text,
            extracted_text=extracted_text,
            need_translation=need_translation,
            parent_id=parent_id,
            index_in_parent=index_in_parent,
            level=level,
            tag=tag,
            attrs=attrs if attrs is not None else {},
            info=info,
            placeholders=placeholders if placeholders is not None else [],
        )

    @staticmethod
    def create_close_marker(
        node_id: str,
        node_type: str,
        unit_type: TranslationUnitType,
        parent_id: Optional[str] = None,
        index_in_parent: int = 0,
        level: int = 0,
        tag: Optional[str] = None,
    ) -> TranslationUnit:
        """Создаёт закрывающий маркер без текста и перевода."""
        return UnitFactory.create(
            node_id=node_id,
            node_type=node_type,
            unit_type=unit_type,
            original_text="",
            extracted_text="",
            need_translation=False,
            parent_id=parent_id,
            index_in_parent=index_in_parent,
            level=level,
            tag=tag,
        )

    @staticmethod
    def extract_node_info(node: SyntaxTreeNode) -> Dict[str, Any]:
        """Извлекает метаданные из узла для создания юнита."""
        node_info = getattr(node, "markup", None) or node.content or ""
        lang_info = getattr(node, "info", "") or None

        # Определяем info поле для структурных блоков
        info_value = None
        if lang_info:
            info_value = str(lang_info)
        elif node_info in ("-", "*", "+"):
            info_value = str(node_info)

        return {
            "level": node.level,
            "tag": node.tag,
            "attrs": dict(node.attrs) if node.attrs else {},
            "info": info_value,
            "content": node.content or "",
        }
