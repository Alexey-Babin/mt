import logging
from typing import List, Optional, Tuple

from markdown_it.tree import SyntaxTreeNode

from mt_server.config import settings

from .node_type import get_unit_type
from .placeholder import PlaceholderManager
from .translation_unit import TranslationUnit
from .translation_unit_type import TranslationUnitType

logger = logging.getLogger("uvicorn.error")


class ASTWalker:
    """Обходит дерево AST Markdown методом DFS, сохраняя полную структуру вложенности."""

    def __init__(self):
        self.units: List[TranslationUnit] = []
        self._node_counter: int = 0

        # Стековая архитектура для поддержки вложенных контекстов перевода.
        # Хранит кортежи: (Активный TranslationUnit, Локальный PlaceholderManager)
        self._context_stack: List[Tuple[TranslationUnit, PlaceholderManager]] = []

    def _generate_node_id(self) -> str:
        """Генерирует уникальный внутренний ID для создаваемых юнитов."""
        self._node_counter += 1
        return f"node_{self._node_counter}"

    def _blocks_qty(self, unit_type: TranslationUnitType):
        return sum(1 for u in self.units if u.unit_type == unit_type)

    def walk(self, root: SyntaxTreeNode) -> List[TranslationUnit]:
        """Точка входа. Обходит дерево и возвращает плоский список юнитов."""
        self.units = []
        self._node_counter = 0
        self._context_stack = []

        logger.debug("Starting AST walk: root type=%s", root.type)

        # Запускаем рекурсивный DFS-обход с корня дерева
        self._traverse(root, parent_id=None, index=0)

        if settings.debug_mode:
            context_blocks = self._blocks_qty(TranslationUnitType.CONTEXT_BLOCK)
            inline_translate = self._blocks_qty(TranslationUnitType.INLINE_TRANSLATE)
            inline_protect = self._blocks_qty(TranslationUnitType.INLINE_PROTECT)
            structural = self._blocks_qty(TranslationUnitType.STRUCTURAL_IGNORE)

            logger.debug(
                "AST walk complete: context_blocks=%d, inline_translate=%d, inline_protect=%d, structural=%d",
                context_blocks,
                inline_translate,
                inline_protect,
                structural,
            )
        return self.units

    def _traverse(
        self, node: SyntaxTreeNode, parent_id: Optional[str] = None, index: int = 0
    ):
        """Рекурсивный метод обхода дерева в глубину (DFS)."""

        # Сначала проверяем тип строки на "root" или "document" БЕЗ вызова get_unit_type,
        # так как у корневого узла 'root' нельзя безопасно читать свойства токенов.
        if node.type in ("root", "document"):
            for idx, child in enumerate(node.children or []):
                self._traverse(child, parent_id=parent_id, index=idx)
            return

        unit_type = get_unit_type(node.type)

        # --- РЕЖИМ НАКОПЛЕНИЯ ТЕКСТА (Если стек контекстов не пуст) ---
        if self._context_stack:
            # Направляем в инлайн-коллектор абсолютно всё,
            # КРОМЕ открытия новых контекстных блоков (например, вложенного heading_open)
            if not (
                unit_type == TranslationUnitType.CONTEXT_BLOCK
                and node.type.endswith("_open")
            ):
                self._collect_inline(node, parent_id, index)
                return

        # --- РЕЖИМ ОБХОДА СТРУКТУРЫ И НАЧАЛА КОНТЕКСТОВ ---
        # Проверяем, является ли узел CONTEXT_BLOCK без суффиксов (например, "paragraph")
        if (
            unit_type == TranslationUnitType.CONTEXT_BLOCK
            and not node.type.endswith("_open")
            and not node.type.endswith("_close")
        ):
            # Это базовый тип блока (например, "paragraph" от SyntaxTreeNode),
            # обрабатываем его как открывающий тег
            self._handle_context_block_open(node, parent_id, index)
        elif unit_type == TranslationUnitType.CONTEXT_BLOCK and node.type.endswith(
            "_open"
        ):
            self._handle_context_block_open(node, parent_id, index)

        elif unit_type == TranslationUnitType.STRUCTURAL_IGNORE:
            # Особая обработка для inline-контейнера: спускаемся внутрь,
            # чтобы обработать дочерние инлайн-элементы (code_inline, strong, em...)
            if node.type == "inline":
                for idx, child in enumerate(node.children or []):
                    self._traverse(child, parent_id=parent_id, index=idx)
                return

            self._handle_structural_block(node, parent_id, index)

        elif unit_type == TranslationUnitType.SPECIAL_CASE:
            self._handle_special_case(node, parent_id, index)

    def _handle_context_block_open(
        self, node: SyntaxTreeNode, parent_id: Optional[str], index: int
    ):
        """Сценарий А (Начало): Инициализирует контейнер и пушит его в стек контекстов."""
        node_id = self._generate_node_id()
        clean_type = node.type.replace("_open", "")
        logger.debug(
            "Context block open: type=%s, node_id=%s, level=%d",
            clean_type,
            node_id,
            node.level,
        )

        context_unit = TranslationUnit(
            node_id=node_id,
            node_type=clean_type,
            unit_type=TranslationUnitType.CONTEXT_BLOCK,
            original_text="",
            extracted_text="",
            need_translation=True,
            parent_id=parent_id,
            index_in_parent=index,
            level=node.level,
            tag=node.tag,
            attrs=dict(node.attrs) if node.attrs else {},
        )
        manager = PlaceholderManager()

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Добавляем юнит в список СРАЗУ, сохраняя DFS порядок
        self.units.append(context_unit)
        self._context_stack.append((context_unit, manager))

        # Рекурсивно спускаемся к детям
        for idx, child in enumerate(node.children):
            self._traverse(child, parent_id=node_id, index=idx)

        # Фиксируем плейсхолдеры после обработки всех дочерних элементов
        # Это необходимо для базовых типов блоков (например, "paragraph"),
        # у которых нет явных _open/_close тегов в AST
        context_unit.placeholders = list(manager.registry.values())
        logger.debug(
            "Context block complete: type=%s, node_id=%s, placeholders_count=%d",
            clean_type,
            node_id,
            len(context_unit.placeholders),
        )

    def _collect_inline(
        self, node: SyntaxTreeNode, parent_id: Optional[str], index: int
    ):
        """Управляет накоплением контента и плейсхолдеров внутри верхнего контекста стека."""
        current_unit, current_manager = self._context_stack[-1]
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

            # Фиксируем все собранные плейсхолдеры из реестра менеджера (сам unit уже лежит в self.units)
            current_unit.placeholders = list(current_manager.registry.values())

            # Добавляем закрывающий пустой маркер-маяк для сохранения иерархии
            node_id = self._generate_node_id()
            close_unit = TranslationUnit(
                node_id=node_id,
                node_type=node.type,
                unit_type=unit_type,
                original_text="",
                extracted_text="",
                need_translation=False,
                parent_id=parent_id,
                index_in_parent=index,
                level=node.level,
                tag=node.tag,
            )
            self.units.append(close_unit)

            # Удаляем закрытый контекст из стека
            self._context_stack.pop()
            return

        # Сценарий Б: Обработка базового текстового узла
        if node.type == "text":
            current_unit.original_text += node.content
            current_unit.extracted_text += node.content
            return

        # Сценарий Б и В: Обработка инлайн-элементов (strong, em, link, code_inline, image...)
        if unit_type in (
            TranslationUnitType.INLINE_TRANSLATE,
            TranslationUnitType.INLINE_PROTECT,
        ):
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
                self._collect_inline(child, parent_id, idx)
            return

        # В самом конце метода _collect_inline для любых других узлов,
        # которые не подошли под условия выше, но оказались внутри абзаца:
        if node.type == "inline":
            for idx, child in enumerate(node.children):
                self._collect_inline(child, parent_id, idx)
            return

    def _handle_structural_block(
        self, node: SyntaxTreeNode, parent_id: Optional[str], index: int
    ):
        """Сценарий Г: Обрабатывает каркас документа (blockquote, list_item), сохраняя маркеры вложенности."""
        node_id = self._generate_node_id()

        node_info = getattr(node, "markup", None) or node.content or ""

        # У токенов fence в markdown-it-py язык кода (например, info = "python") лежит в поле node.info
        # Вытаскиваем его, чтобы reconstructor знал язык подсветки синтаксиса
        lang_info = getattr(node, "info", "") or None

        logger.debug(
            "Structural block: type=%s, node_id=%s, level=%d",
            node.type,
            node_id,
            node.level,
        )

        unit = TranslationUnit(
            node_id=node_id,
            node_type=node.type,
            unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
            original_text=node.content or "",
            extracted_text=node.content or "",
            need_translation=False,
            parent_id=parent_id,
            index_in_parent=index,
            level=node.level,
            tag=node.tag,
            attrs=dict(node.attrs) if node.attrs else {},
            info=str(lang_info)
            if lang_info
            else (str(node_info) if node_info in ("-", "*", "+") else None),
        )
        self.units.append(unit)

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Если это одиночный блок кода/математики/HTML,
        # мы полностью БЛОКИРУЕМ рекурсивный спуск в его детей, предотвращая дублирование в списке units
        if node.type in ("fence", "code_block", "math_block", "html_block"):
            return

        # Для всех остальных парных структурных блоков (цитаты, списки) спускаемся к детям,
        # только если это открывающий тег
        if not node.type.endswith("_close"):
            for idx, child in enumerate(node.children):
                self._traverse(child, parent_id=node_id, index=idx)

    def _handle_special_case(
        self, node: SyntaxTreeNode, parent_id: Optional[str], index: int
    ):
        """Сценарий Д: Обрабатывает Front Matter метаданные."""
        node_id = self._generate_node_id()

        logger.debug("Special case: type=%s, node_id=%s", node.type, node_id)

        special_unit = TranslationUnit(
            node_id=node_id,
            node_type=node.type,
            unit_type=TranslationUnitType.SPECIAL_CASE,
            original_text=node.content or "",
            extracted_text=node.content or "",
            need_translation=False,
            parent_id=parent_id,
            index_in_parent=index,
            level=node.level,
        )
        self.units.append(special_unit)
