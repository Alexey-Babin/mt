from typing import List, Optional

from markdown_it.tree import SyntaxTreeNode

from .node_type import get_unit_type
from .placeholder import PlaceholderManager
from .translation_unit import TranslationUnit
from .translation_unit_type import TranslationUnitType


class ASTWalker:
    """Обходит дерево AST Markdown и формирует плоский список TranslationUnit."""

    def __init__(self):
        self.units: List[TranslationUnit] = []
        self._node_counter: int = 0

    def _generate_node_id(self) -> str:
        """Генерирует уникальный внутренний ID для создаваемых юнитов."""
        self._node_counter += 1
        return f"node_{self._node_counter}"

    def walk(self, root: SyntaxTreeNode) -> List[TranslationUnit]:
        """Точка входа. Обходит дерево и возвращает заполненный список юнитов."""
        self.units = []
        self._node_counter = 0

        # Запускаем обход с корневого узла
        self._traverse(root, parent_id=None, index=0)
        return self.units

    def _traverse(
        self, node: SyntaxTreeNode, parent_id: Optional[str] = None, index: int = 0
    ):
        """Рекурсивно обходит каркас документа.

        Отвечает за поиск CONTEXT_BLOCK и SPECIAL_CASE, игнорируя структурный шум.
        """
        unit_type = get_unit_type(node.type)

        # Сценарий 1: Нашли начало текстового контейнера (абзац, заголовок, ячейка)
        if unit_type == TranslationUnitType.CONTEXT_BLOCK and node.type.endswith(
            "_open"
        ):
            node_id = self._generate_node_id()
            clean_type = node.type.replace("_open", "")

            # Создаем юнит для всего контейнера целиком
            unit = TranslationUnit(
                node_id=node_id,
                node_type=clean_type,
                unit_type=unit_type,
                original_text="",
                extracted_text="",
                parent_id=parent_id,
                index_in_parent=index,
                level=node.level,
                tag=node.tag,
                attrs=dict(node.attrs) if node.attrs else {},
                need_translation=True,
            )

            # Инициализируем локальный менеджер плейсхолдеров для этого абзаца
            manager = PlaceholderManager()

            # Сканируем ВСЕХ детей этого контейнера на предмет текста и инлайнов
            for child in node.children:
                self._collect_inline_content(child, unit, manager)

            # Переносим собранные плейсхолдеры из реестра менеджера в юнит
            unit.placeholders = list(manager.registry.values())
            self.units.append(unit)
            return  # Важно: мы полностью обработали этот блок и его детей, глубже идти не нужно

        # Сценарий 2: Нашли метаданные (Front Matter)
        if unit_type == TranslationUnitType.SPECIAL_CASE:
            self._handle_special_case(node, parent_id, index)
            return

        # Сценарий 3: Структурные узлы (документ, списки, таблицы, а также закрывающие теги)
        # Просто проваливаемся глубже к их детям
        for idx, child in enumerate(node.children):
            self._traverse(child, parent_id=parent_id, index=idx)

    def _collect_inline_content(
        self, node: SyntaxTreeNode, unit: TranslationUnit, manager: PlaceholderManager
    ):
        """Рекурсивно собирает текст и инлайн-разметку внутри одного CONTEXT_BLOCK.

        Эта функция не создает новые TranslationUnit, она наполняет переданный unit.
        """
        unit_type = get_unit_type(node.type)

        # Атомарный текст
        if node.type == "text":
            unit.original_text += node.content
            unit.extracted_text += node.content
            return

        # Инлайн разметка (переводимая или защищенная)
        if unit_type in (
            TranslationUnitType.INLINE_TRANSLATE,
            TranslationUnitType.INLINE_PROTECT,
        ):
            # Просим менеджер создать плейсхолдер и зафиксировать маску
            ph = manager.create_placeholder(node)
            unit.extracted_text += ph.tag_mask

            # Если это строка (стили вроде **), пишем в оригинальный текст
            if isinstance(ph.original_markup, str):
                unit.original_text += ph.original_markup

            # ВАЖНО: Если у инлайна есть свои дети (например текст внутри **жирного**),
            # мы обязаны собрать их контент ТУДА ЖЕ, в этот же unit.
            for child in node.children:
                self._collect_inline_content(child, unit, manager)
            return

        # Служебные узлы внутри абзаца (например, токен 'inline' от markdown-it)
        # Проходим сквозь них к их детям
        for child in node.children:
            self._collect_inline_content(child, unit, manager)

    def _handle_special_case(
        self, node: SyntaxTreeNode, parent_id: Optional[str], index: int
    ):
        """Обрабатывает узлы метаданных Front Matter."""
        node_id = self._generate_node_id()
        special_unit = TranslationUnit(
            node_id=node_id,
            node_type=node.type,
            unit_type=TranslationUnitType.SPECIAL_CASE,
            original_text=node.content or "",
            extracted_text=node.content or "",
            parent_id=parent_id,
            index_in_parent=index,
            level=node.level,
            need_translation=False,  # Четко изолируем от общего потока чанков
        )
        self.units.append(special_unit)
