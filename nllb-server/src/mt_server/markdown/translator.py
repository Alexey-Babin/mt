from __future__ import annotations

from markdown_it.renderer import RendererHTML
from markdown_it.token import Token

from mt_server.markdown.extractor import MarkdownTranslationUnitExtractor
from mt_server.markdown.units import TranslationUnit


class MarkdownTranslator:
    def __init__(self, translator):
        self.translator = translator
        self.extractor = MarkdownTranslationUnitExtractor()

    def translate(
        self,
        text: str,
        src_lang: str,
        tgt_lang: str,
    ) -> str:
        tokens, units = self.extractor.extract(text)

        if not units:
            # если по результатам разбора нет юнитов для перевода, возвращаем исходный текст
            return text

        translated_units = self._translate_units(
            units=units,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
        )

        self._apply_translations(
            tokens=tokens,
            units=translated_units,
        )

        return self._render(tokens)

    def _translate_units(
        self,
        units: list[TranslationUnit],
        src_lang: str,
        tgt_lang: str,
    ) -> list[TranslationUnit]:
        translated_units: list[TranslationUnit] = []

        for unit in units:
            translated_text = self.translator.translate(
                text=unit.text,
                src_lang=src_lang,
                tgt_lang=tgt_lang,
            )

            translated_unit = TranslationUnit(
                id=unit.id,
                type=unit.type,
                text=translated_text,
                inline_token_index=unit.inline_token_index,
                placeholders=unit.placeholders,
                metadata=unit.metadata,
            )
            translated_units.append(translated_unit)

        return translated_units

    @staticmethod
    def _apply_translations(
        tokens: list[Token],
        units: list[TranslationUnit],
    ) -> None:
        for unit in units:
            token = tokens[unit.inline_token_index]
            token.content = unit.text

            if token.children:
                token.children = None

    @staticmethod
    def _render(tokens: list[Token]) -> str:
        renderer = RendererHTML()
        return renderer.render(tokens, {}, {})
