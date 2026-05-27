from dataclasses import dataclass, field
from typing import List, Optional

from .placeholder import Placeholder
from .translation_unit_type import TranslationUnitType


@dataclass
class TranslationUnit:
    """Единица перевода с метаданными."""

    # Идентификация
    node_id: str
    node_type: str
    unit_type: TranslationUnitType

    # Текст для перевода
    original_text: str
    extracted_text: str
    translated_text: Optional[str] = None

    # Управление конвейером перевода
    need_translation: bool = True  # Сигнал для Chunking Engine

    # Плейсхолдеры (ИСПРАВЛЕНО: теперь безопасно для памяти)
    placeholders: List[Placeholder] = field(default_factory=list)

    # Позиция в AST
    parent_id: Optional[str] = None
    index_in_parent: Optional[int] = None
    level: int = 0

    # Метаданные
    attrs: Optional[dict] = None
    tag: Optional[str] = None
    info: Optional[str] = None

    # Статус
    is_translated: bool = False
    has_errors: bool = False
    error_message: Optional[str] = None
