from typing import Dict

from .translation_unit_type import TranslationUnitType

# === ГРУППЫ ТОКЕНОВ ДЛЯ ДИНАМИЧЕСКОЙ СБОРКИ СЛОВАРЯ ===

# 1. Текстовые контейнеры (Блоки)
_BLOCK_TYPES = {
    "paragraph",
    "heading",
    "th",
    "td",
    "dt",
    "dd",
    "footnote",
    "field_name",
    "field_body",  # Из field_list_plugin
}

# 2. Инлайн-теги разметки, текст внутри которых переводится
_INLINE_TRANSLATE_PAIRED = {"strong", "em", "s", "link"}
_INLINE_TRANSLATE_SINGLE = {"image"}

# 3. Атомарные инлайны, которые защищаются плейсхолдером целиком
_INLINE_PROTECT_TYPES = {
    "code_inline",
    "math_inline",
    "html_inline",
    "footnote_ref",
    "tasklist_item",
    "softbreak",
    "hardbreak",
}

# 4. Структурные контейнеры и крупные блоки кода/математики (текст игнорируется)
_STRUCTURAL_BLOCKS = {
    "fence",
    "code_block",
    "math_block",
    "html_block",
    "table",
    "thead",
    "tbody",
    "tr",
    "blockquote",
    "bullet_list",
    "ordered_list",
    "list_item",
    "footnote_block",
    "dl",
    "field_list",
    "field",  # Контейнер из field_list_plugin
}


# === ИНИЦИАЛИЗАЦИЯ И СБОРКА NODE_TYPE_MAP ===

_NODE_TYPE_MAP: Dict[str, TranslationUnitType] = {}

# Заполняем блоки (как open, так и close переводят в режим сборки контекста)
for block in _BLOCK_TYPES:
    _NODE_TYPE_MAP[f"{block}_open"] = TranslationUnitType.CONTEXT_BLOCK
    _NODE_TYPE_MAP[f"{block}_close"] = TranslationUnitType.CONTEXT_BLOCK

# Заполняем транслируемый инлайн open/close
for inline in _INLINE_TRANSLATE_PAIRED:
    _NODE_TYPE_MAP[f"{inline}_open"] = TranslationUnitType.INLINE_TRANSLATE
    _NODE_TYPE_MAP[f"{inline}_close"] = TranslationUnitType.INLINE_TRANSLATE

# Заполняем защищаемые атомарные инлайны (одиночные токены)
for inline in _INLINE_PROTECT_TYPES:
    _NODE_TYPE_MAP[inline] = TranslationUnitType.INLINE_PROTECT

# Заполняем одиночные транслируемые инлайны (БЕЗ суффиксов)
for inline in _INLINE_TRANSLATE_SINGLE:
    _NODE_TYPE_MAP[inline] = TranslationUnitType.INLINE_TRANSLATE

# ИСПРАВЛЕНО: Разделяем парные и одиночные структурные блоки
_PARSED_STRUCTURAL_BLOCKS = {
    "table",
    "thead",
    "tbody",
    "tr",
    "blockquote",
    "bullet_list",
    "ordered_list",
    "list_item",
    "footnote_block",
    "dl",
    "field_list",
    "field",
}
_SINGLE_STRUCTURAL_BLOCKS = {"fence", "code_block", "math_block", "html_block"}

# Заполняем структурные контейнеры open/close
for block in _PARSED_STRUCTURAL_BLOCKS:
    _NODE_TYPE_MAP[f"{block}_open"] = TranslationUnitType.STRUCTURAL_IGNORE
    _NODE_TYPE_MAP[f"{block}_close"] = TranslationUnitType.STRUCTURAL_IGNORE

# Заполняем одиночные структурные блоки СТРОГО без суффиксов
for block in _SINGLE_STRUCTURAL_BLOCKS:
    _NODE_TYPE_MAP[block] = TranslationUnitType.STRUCTURAL_IGNORE

# Служебные одиночные токены и исключения
_NODE_TYPE_MAP["text"] = TranslationUnitType.INLINE_TRANSLATE
_NODE_TYPE_MAP["inline"] = TranslationUnitType.STRUCTURAL_IGNORE
_NODE_TYPE_MAP["document"] = TranslationUnitType.STRUCTURAL_IGNORE
_NODE_TYPE_MAP["hr"] = TranslationUnitType.STRUCTURAL_IGNORE
_NODE_TYPE_MAP["front_matter"] = TranslationUnitType.SPECIAL_CASE


def get_unit_type(node_type: str) -> TranslationUnitType:
    return _NODE_TYPE_MAP.get(node_type, TranslationUnitType.STRUCTURAL_IGNORE)
