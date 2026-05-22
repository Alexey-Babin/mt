from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TranslationUnitType(StrEnum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST_ITEM = "list_item"
    BLOCKQUOTE = "blockquote"
    TABLE_CELL = "table_cell"
    IMAGE_ALT = "image_alt"


@dataclass(slots=True)
class Placeholder:
    key: str
    kind: str
    value: Any


@dataclass(slots=True)
class TranslationUnit:
    id: str
    type: TranslationUnitType
    text: str

    # Ссылки на markdown-it tokens
    inline_token_index: int

    # placeholders, которые были вынесены из markdown
    placeholders: list[Placeholder] = field(default_factory=list)

    # Дополнительные данные
    metadata: dict[str, Any] = field(default_factory=dict)
