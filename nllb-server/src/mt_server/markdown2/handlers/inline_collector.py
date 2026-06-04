"""Модуль для сбора инлайн-элементов внутри контекстных блоков."""

import logging
from typing import TYPE_CHECKING, Optional

from markdown_it.tree import SyntaxTreeNode

from ..node_type import get_unit_type
from ..translation_unit_type import TranslationUnitType

if TYPE_CHECKING:
    from ..ast_walker import ASTWalker

logger = logging.getLogger("uvicorn.error")


class InlineCollector:
    """Собирает текст и плейсхолдеры внутри контекстного блока."""

    def __init__(self, walker: "ASTWalker"):
        self._walker = walker

    def collect(
        self,
        node: SyntaxTreeNode,
        parent_id: Optional[str],
        index: int,
    ):
        """Управляет накоплением контента и плейсхолдеров внутри верхнего контекста стека."""
        if not self._walker._context_block_handler.has_active_context:
            return

        current_unit, current_manager = (
            self._walker._context_block_handler.current_context
        )
        unit_type = get_unit_type(node.type)

        # Узел inline - контейнер для инлайн-элементов, обрабатываем его детей
        if node.type == "inline":
            for idx, child in enumerate(node.children or []):
                self.collect(child, parent_id, idx)
            return

        unit_type = get_unit_type(node.type)
        # Сценарий А (Конец): Наткнулись на закрывающий тег контекстного блока
        if unit_type == TranslationUnitType.CONTEXT_BLOCK and node.type.endswith(
            "_close"
        ):
            logger.debug(
                "Context block close: type=%s, node_id=%s, text_length=%d",
                current_unit.node_type,
                current_unit.node_id,
                len(current_unit.extracted_text),
            )

            # Фиксируем все собранные плейсхолдеры из реестра менеджера
            current_unit.placeholders = list(current_manager.registry.values())

            # Добавляем закрывающий пустой маркер-маяк для сохранения иерархии
            node_id = self._walker._generate_node_id()
            close_unit = self._walker._unit_factory.create_close_marker(
                node_id=node_id,
                node_type=node.type,
                unit_type=unit_type,
                parent_id=parent_id,
                index_in_parent=index,
                level=node.level,
                tag=node.tag,
            )
            self._walker.units.append(close_unit)

            # Удаляем закрытый контекст из стека через handler
            self._walker._context_block_handler._context_stack.pop()
            return

        # Сценарий Б: Обработка базового текстового узла
        if node.type == "text":
            current_unit.original_text += node.content
            current_unit.extracted_text += node.content
            return

        # Сценарий Б и В: Обработка инлайн-элементов
        if unit_type in (
            TranslationUnitType.INLINE_TRANSLATE,
            TranslationUnitType.INLINE_PROTECT,
        ):
            self._handle_inline_element(
                node, parent_id, index, current_manager, current_unit
            )
            return

    def _handle_inline_element(
        self,
        node: SyntaxTreeNode,
        parent_id: Optional[str],
        index: int,
        current_manager,
        current_unit,
    ):
        """Обрабатывает инлайн-элемент (strong, em, link, code_inline, image...)."""
        # Пропускаем явные _close теги для парных инлайнов
        if (
            node.type.endswith("_close")
            and get_unit_type(node.type) == TranslationUnitType.INLINE_TRANSLATE
        ):
            return

        ph = current_manager.create_placeholder(node)

        logger.debug(
            "Inline element: type=%s, mask=%s, strategy=%s",
            node.type,
            ph.tag_mask.strip(),
            ph.strategy,
        )

        # Очищаем маску от внешних служебных пробелов (.strip()), делая её вида {s_1}
        clean_mask = ph.tag_mask.strip()
        current_unit.extracted_text += clean_mask

        if isinstance(ph.original_markup, str):
            current_unit.original_text += ph.original_markup

        # Рекурсивно сканируем детей инлайна
        for idx, child in enumerate(node.children):
            self.collect(child, parent_id, idx)

        # Для парных тегов с стратегией INLINE_TRANSLATE создаём закрывающий placeholder
        if ph.strategy == "INLINE_TRANSLATE" and not ph.is_closing:
            close_ph = current_manager._create_closing_placeholder(
                ph, prefix=current_manager._get_short_prefix(node.type)
            )
            close_clean_mask = close_ph.tag_mask.strip()
            current_unit.extracted_text += close_clean_mask
            logger.debug(
                "Added closing placeholder for paired inline: mask=%s",
                close_clean_mask,
            )
