import logging
from typing import List, Optional

from markdown_it.tree import SyntaxTreeNode

from mt_server.config import settings

from .handlers import (
    ContextBlockHandler,
    InlineCollector,
    SpecialCaseHandler,
    StructuralBlockHandler,
)
from .translation_unit import TranslationUnit
from .translation_unit_type import TranslationUnitType
from .unit_factory import UnitFactory

logger = logging.getLogger("uvicorn.error")


class ASTWalker:
    """Обходит дерево AST Markdown методом DFS, сохраняя полную структуру вложенности.

    Использует архитектуру handlers для делегирования обработки различных типов узлов:
    - ContextBlockHandler: абзацы, заголовки, ячейки таблиц
    - StructuralBlockHandler: списки, цитаты, блоки кода
    - SpecialCaseHandler: Front Matter и другие исключения
    - InlineCollector: сбор текста и плейсхолдеров внутри контекстов
    """

    def __init__(self):
        self.units: List[TranslationUnit] = []
        self._node_counter: int = 0

        # Handlers для различных типов узлов
        self._context_block_handler: ContextBlockHandler = None  # type: ignore[assignment]
        self._structural_handler: StructuralBlockHandler = None  # type: ignore[assignment]
        self._special_case_handler: SpecialCaseHandler = None  # type: ignore[assignment]
        self._inline_collector: InlineCollector = None  # type: ignore[assignment]
        self._unit_factory: UnitFactory = UnitFactory()

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

        # Инициализируем handlers для каждого прохода
        self._context_block_handler = ContextBlockHandler(self)
        self._structural_handler = StructuralBlockHandler(self)
        self._special_case_handler = SpecialCaseHandler(self)
        self._inline_collector = InlineCollector(self)

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
        """Рекурсивный метод обхода дерева в глубину (DFS).

        Делегирует обработку узлов соответствующим handlers:
        1. Корневые узлы (root/document) - обрабатываются напрямую
        2. Контекстные блоки - ContextBlockHandler
        3. Структурные блоки - StructuralBlockHandler
        4. Специальные случаи - SpecialCaseHandler
        """
        # Сначала проверяем тип строки на "root" или "document" БЕЗ вызова get_unit_type,
        # так как у корневого узла 'root' нельзя безопасно читать свойства токенов.
        if node.type in ("root", "document"):
            for idx, child in enumerate(node.children or []):
                self._traverse(child, parent_id=parent_id, index=idx)
            return

        # Узел inline - контейнер для инлайн-элементов внутри paragraph
        # Важно: сам узел inline имеет тип structural_ignore, но его дети должны быть обработаны
        if node.type == "inline":
            # Делегируем обработку детей InlineCollector для сбора текста и плейсхолдеров
            self._collect_inline(node, parent_id, index)
            return

        # Пробуем обработать через handlers по приоритету
        # 1. Контекстные блоки (абзацы, заголовки) - имеют наивысший приоритет
        if self._context_block_handler.handle_node(node, parent_id, index):
            return

        # 2. Структурные блоки (списки, цитаты, код)
        if self._structural_handler.handle_node(node, parent_id, index):
            return

        # 3. Специальные случаи (Front Matter)
        if self._special_case_handler.handle_node(node, parent_id, index):
            return

    def _collect_inline(
        self, node: SyntaxTreeNode, parent_id: Optional[str], index: int
    ):
        """Делегирует сбор инлайн-элементов в InlineCollector."""
        self._inline_collector.collect(node, parent_id, index)
