from enum import Enum


class TranslationUnitType(Enum):
    """Стратегия обработки узла AST в системе перевода."""

    # Текстовый контейнер (переводится целиком как абзац)
    CONTEXT_BLOCK = "context_block"
    # Inline-элемент, текст внутри которого переводится
    INLINE_TRANSLATE = "inline_translate"
    # Нетранслируемый инлайн (изолируется плейсхолдером)
    INLINE_PROTECT = "inline_protect"
    # Структурный шум (сохраняет каркас, не содержит текста)
    STRUCTURAL_IGNORE = "structural_ignore"
    # Требует кастомной логики (например, Front Matter)
    SPECIAL_CASE = "special_case"
