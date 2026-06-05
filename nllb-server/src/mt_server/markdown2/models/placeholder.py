from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Union

from markdown_it.tree import SyntaxTreeNode

from .node_type import get_unit_type
from .translation_unit_type import TranslationUnitType


@dataclass
class Placeholder:
    """Метаданные плейсхолдера для изоляции непереводимых элементов."""

    id: int
    tag_mask: str
    strategy: Literal["INLINE_TRANSLATE", "INLINE_PROTECT"]
    node_type: str

    # Содержимое для восстановления
    original_markup: Union[str, Dict[str, Any]]
    is_closing: bool = False


class PlaceholderManager:
    """Управляет плейсхолдерами в рамках одного контекстного блока (абзаца/ячейки)."""

    def __init__(self):
        self._counter: int = 0
        self.registry: Dict[str, Placeholder] = {}

        # Хранилище активных открытых ID для парных тегов (LIFO стек)
        self._open_tags_stacks: Dict[str, List[int]] = {}

    def _determine_strategy(
        self, unit_type: TranslationUnitType
    ) -> Literal["INLINE_TRANSLATE", "INLINE_PROTECT"]:
        """Определяет строковую стратегию на основе Enum."""
        if unit_type == TranslationUnitType.INLINE_TRANSLATE:
            return "INLINE_TRANSLATE"
        return "INLINE_PROTECT"

    def _get_short_prefix(self, node_type: str) -> str:
        """Генерирует короткий читаемый префикс для маски NLLB."""
        base_type = node_type.replace("_open", "").replace("_close", "")

        mapping = {
            "strong": "s",
            "em": "e",
            "link": "lnk",
            "image": "img",
            "code_inline": "code",
            "math_inline": "math",
            "html_inline": "html",
            "footnote_ref": "fn",
            "tasklist_item": "chk",
            "softbreak": "br",
            "hardbreak": "br",
        }
        return mapping.get(base_type, "ph")

    def _is_tasklist_checkbox(self, node: SyntaxTreeNode) -> bool:
        """Проверяет, является ли html_inline токеном чекбокса task-list."""
        if node.type != "html_inline":
            return False
        content = node.content or ""
        return 'class="task-list-item-checkbox"' in content

    def create_placeholder(self, node: SyntaxTreeNode) -> Placeholder:
        """Создает placeholder из узла AST, извлекая оригинальную разметку."""
        # Особая обработка для task-list checkbox - трактуем как tasklist_item
        if self._is_tasklist_checkbox(node):
            unit_type = TranslationUnitType.INLINE_PROTECT
            strategy = "INLINE_PROTECT"
            prefix = "chk"
            is_closing = False
        else:
            unit_type = get_unit_type(node.type)
            strategy = self._determine_strategy(unit_type)
            is_closing = node.type.endswith("_close")
            prefix = self._get_short_prefix(node.type)

        # 1. Синхронизация ID для парных и одиночных тегов
        if is_closing:
            stack = self._open_tags_stacks.get(prefix, [])
            if stack:
                current_id = stack.pop()
            else:
                self._counter += 1
                current_id = self._counter

            tag_mask = f" {{/{prefix}_{current_id}}} "
        else:
            self._counter += 1
            current_id = self._counter
            tag_mask = f" {{{prefix}_{current_id}}} "

            # Запоминаем ID в стек только для открывающих тегов транслируемой разметки
            # НЕ добавляем в стек, если это искусственно созданный закрывающий плейсхолдер
            if strategy == "INLINE_TRANSLATE":
                if prefix not in self._open_tags_stacks:
                    self._open_tags_stacks[prefix] = []
                self._open_tags_stacks[prefix].append(current_id)

        # 2. Извлечение оригинального контента (original_markup)
        original_markup: Union[str, Dict[str, Any]] = ""

        if strategy == "INLINE_PROTECT":
            # Особая обработка для task-list checkbox
            if self._is_tasklist_checkbox(node):
                # Сохраняем полный HTML чекбокса для восстановления
                original_markup = node.content or ""
            elif node.type == "code_inline":
                original_markup = f"`{node.content}`"
            elif node.type == "math_inline":
                original_markup = f"${node.content}$"
            elif node.type in ("softbreak", "hardbreak"):
                original_markup = "\n" if node.type == "softbreak" else "<br>"
            else:
                original_markup = node.content or ""

        elif strategy == "INLINE_TRANSLATE":
            if node.type == "link" or node.type.startswith("link_"):
                if is_closing:
                    original_markup = ""
                else:
                    # Извлекаем атрибуты ссылки для воссоздания синтаксиса [текст](url)
                    # node.attrs в markdown-it-py - это обычный dict
                    original_markup = {
                        "href": node.attrs.get("href", "") if node.attrs else "",
                        "title": node.attrs.get("title", "") if node.attrs else "",
                    }
            elif node.type == "image":
                # Особый случай: одиночный токен, но ведет себя как INLINE_TRANSLATE,
                # так как node.content (Alt-текст) будет переводиться внутри масок.
                original_markup = {
                    "src": node.attrs.get("src", "") if node.attrs else "",
                    "title": node.attrs.get("title", "") if node.attrs else "",
                }
            else:
                # Для strong, em, s - сохраняем маркер только в ОТКРЫВАЮЩЕМ теге.
                # Закрывающий тег разметку не содержит (она закроется автоматически).
                if is_closing:
                    original_markup = ""
                else:
                    fallback = {"strong": "**", "em": "*", "s": "~~"}.get(prefix, "**")
                    original_markup = getattr(node, "markup", None) or fallback

        # 3. Сборка объекта
        placeholder = Placeholder(
            id=current_id,
            tag_mask=tag_mask,
            strategy=strategy,
            node_type=node.type,
            original_markup=original_markup,
            is_closing=is_closing,
        )

        self.registry[tag_mask.strip()] = placeholder
        return placeholder

    def _create_closing_placeholder(
        self, open_ph: Placeholder, prefix: str
    ) -> Placeholder:
        """Создаёт закрывающий placeholder для парного тега с тем же ID.

        Используется когда markdown-it-py объединяет strong_open/strong_close
        в один узел strong, но нам нужны оба placeholder для корректного восстановления.
        """
        current_id = open_ph.id
        tag_mask = f" {{/{prefix}_{current_id}}} "

        # Закрывающий тег не содержит оригинальной разметки, НО для ссылок (link)
        # нужно сохранить original_markup из открывающего тега для восстановления URL
        original_markup = open_ph.original_markup if prefix == "lnk" else ""

        # Сборка объекта - используем тот же node_type что и у открывающего тега
        # (для сильных это 'strong', для ссылок это 'link_open')
        placeholder = Placeholder(
            id=current_id,
            tag_mask=tag_mask,
            strategy=open_ph.strategy,
            node_type=open_ph.node_type,  # Сохраняем оригинальный node_type
            original_markup=original_markup,
            is_closing=True,
        )

        self.registry[tag_mask.strip()] = placeholder
        return placeholder
