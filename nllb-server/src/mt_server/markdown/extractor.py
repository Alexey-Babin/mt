from __future__ import annotations

from markdown_it import MarkdownIt
from markdown_it.token import Token

from mt_server.markdown.placeholders import InlinePlaceholderExtractor
from mt_server.markdown.units import TranslationUnit, TranslationUnitType

TRANSLATABLE_INLINE_PARENTS = {
    "paragraph_open": TranslationUnitType.PARAGRAPH,
    "heading_open": TranslationUnitType.HEADING,
    "blockquote_open": TranslationUnitType.BLOCKQUOTE,
}


LIST_ITEM_PARENTS = {
    "list_item_open",
}


TABLE_CELL_PARENTS = {
    "td_open",
    "th_open",
}


class MarkdownTranslationUnitExtractor:
    def __init__(self):
        self.md = MarkdownIt("commonmark", {"html": False})
        self.placeholder_extractor = InlinePlaceholderExtractor()

    def parse(self, text: str) -> list[Token]:
        return self.md.parse(text)

    def extract(self, text: str) -> tuple[list[Token], list[TranslationUnit]]:
        tokens = self.parse(text)
        units: list[TranslationUnit] = []

        for ix, token in enumerate(tokens):
            if token.type != "inline":
                continue

            parent_type = self._detect_parent_type(tokens, ix)
            if parent_type is None:
                continue

            extracted_text, placeholders = self.placeholder_extractor.extract(token)

            if not extracted_text.strip() and not placeholders:
                continue

            units.append(
                TranslationUnit(
                    id=f"tu_{len(units)}",
                    type=parent_type,
                    text=extracted_text,
                    inline_token_index=ix,
                    placeholders=placeholders,
                )
            )

        return tokens, units

    @staticmethod
    def _detect_parent_type(
        tokens: list[Token],
        inline_index: int,
    ) -> TranslationUnitType | None:
        # Пока не встретим parent, который не inline
        for i in range(inline_index - 1, -1, -1):
            parent = tokens[i]

            if parent.type in TRANSLATABLE_INLINE_PARENTS:
                return TRANSLATABLE_INLINE_PARENTS[parent.type]

            if parent.type in LIST_ITEM_PARENTS:
                return TranslationUnitType.LIST_ITEM

            if parent.type in TABLE_CELL_PARENTS:
                return TranslationUnitType.TABLE_CELL

            # Если встретили блок, который не является parent для inline, прекращаем поиск (??)
            if (
                parent.type.endswith("_open")
                and parent.type not in TRANSLATABLE_INLINE_PARENTS
            ):
                break

        return None
