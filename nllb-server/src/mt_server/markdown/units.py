# src/mt_server/markdown/units.py

import logging
from dataclasses import dataclass, field
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class MarkdownTranslationUnit:
    """
    Единица перевода: атомарный блок текста внутри Markdown.
    Соответствует одному HTML-блоку (p, h1-h6, li, td) после конвертации.

    Attributes:
        id: Уникальный идентификатор в рамках документа.
        text: Чистый текст для перевода (без HTML-тегов).
        metadata: Служебная информация (тип блока, оригинальный HTML, индекс).
    """

    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.text.strip():
            logger.warning(
                f"Unit {self.id} created with empty or whitespace-only text."
            )
