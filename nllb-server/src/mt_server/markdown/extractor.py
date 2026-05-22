from __future__ import annotations

import logging

from markdown_it import MarkdownIt
from markdown_it.token import Token

from mt_server.markdown.placeholders import extract_translatable_segments
from mt_server.markdown.units import TranslationUnit, TranslationUnitType

logger = logging.getLogger("uvicorn.error")

TRANSLATABLE_INLINE_PARENTS = {
    "paragraph_open": TranslationUnitType.PARAGRAPH,
    "heading_open": TranslationUnitType.HEADING,
    "blockquote_open": TranslationUnitType.BLOCKQUOTE,
}

LIST_ITEM_PARENTS = {"list_item_open"}
TABLE_CELL_PARENTS = {"td_open", "th_open"}


class MarkdownTranslationUnitExtractor:
    def __init__(self):
        self.md = MarkdownIt("commonmark", {"html": False})

    def parse(self, text: str) -> list[Token]:
        return self.md.parse(text)

    def extract(self, text: str) -> tuple[list[Token], list[TranslationUnit]]:
        tokens = self.parse(text)
        units: list[TranslationUnit] = []

        logger.debug(f"Total tokens: {len(tokens)}")

        for ix, token in enumerate(tokens):
            logger.debug(f"Token {ix}: type={token.type}, content={token.content!r}")

            if token.type != "inline":
                continue

            parent_type = self._detect_parent_type(tokens, ix)
            logger.debug(f"  parent_type={parent_type}")

            if parent_type is None:
                continue

            # Разбиваем на сегменты
            segments = extract_translatable_segments(token)
            logger.debug(f"  segments={[(s.text, s.translatable) for s in segments]}")

            # Есть ли вообще что переводить?
            has_translatable = any(s.translatable and s.text.strip() for s in segments)
            if not has_translatable:
                logger.debug("  no translatable segments, skipping")
                continue

            # Сохраняем исходный текст юнита для отладки
            raw_text = token.content

            units.append(
                TranslationUnit(
                    id=f"tu_{len(units)}",
                    type=parent_type,
                    text=raw_text,
                    inline_token_index=ix,
                    placeholders=[],  # больше не используем
                    metadata={"segments": segments},
                )
            )
            logger.debug(f"  created unit id=tu_{len(units) - 1}")

        return tokens, units

    @staticmethod
    def _detect_parent_type(
        tokens: list[Token],
        inline_index: int,
    ) -> TranslationUnitType | None:
        for i in range(inline_index - 1, -1, -1):
            parent = tokens[i]

            if parent.type in TRANSLATABLE_INLINE_PARENTS:
                return TRANSLATABLE_INLINE_PARENTS[parent.type]

            if parent.type in LIST_ITEM_PARENTS:
                return TranslationUnitType.LIST_ITEM

            if parent.type in TABLE_CELL_PARENTS:
                return TranslationUnitType.TABLE_CELL

            if (
                parent.type.endswith("_open")
                and parent.type not in TRANSLATABLE_INLINE_PARENTS
            ):
                return None

        return None
