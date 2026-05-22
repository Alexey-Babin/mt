from __future__ import annotations

import logging

from mt_server.markdown.extractor import MarkdownTranslationUnitExtractor
from mt_server.markdown.placeholders import render_segments
from mt_server.markdown.restorer import MarkdownRestorer
from mt_server.markdown.units import TranslationUnit

logger = logging.getLogger("uvicorn.error")


class MarkdownTranslator:
    def __init__(self, translator):
        self.translator = translator
        self.extractor = MarkdownTranslationUnitExtractor()
        self.restorer = MarkdownRestorer()

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        logger.debug(f"Translating markdown, src={src_lang}, tgt={tgt_lang}")
        logger.debug(f"Input text: {text!r}")

        tokens, units = self.extractor.extract(text)
        logger.debug(f"Extracted {len(units)} units")

        if not units:
            logger.debug("No units found, returning original text")
            return text

        translated_units = self._translate_units(
            units=units,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
        )

        result = self.restorer.restore(tokens, translated_units)
        logger.debug(f"Rendered result: {result!r}")
        return result

    def _translate_units(
        self,
        units: list[TranslationUnit],
        src_lang: str,
        tgt_lang: str,
    ) -> list[TranslationUnit]:
        translated_units: list[TranslationUnit] = []

        for unit in units:
            logger.debug(f"Translating unit {unit.id}: segments from {unit.text!r}")

            def make_translate_fn(sl: str, tl: str):
                """Замыкание, чтобы не захватить переменные цикла."""

                def fn(text: str) -> str:
                    return self.translator.translate(
                        text=text,
                        src_lang=sl,
                        tgt_lang=tl,
                    )

                return fn

            translated_text = render_segments(
                segments=unit.metadata.get("segments", []),
                translate_fn=make_translate_fn(src_lang, tgt_lang),
            )

            logger.debug(f"Translated unit {unit.id}: {translated_text!r}")

            translated_units.append(
                TranslationUnit(
                    id=unit.id,
                    type=unit.type,
                    text=translated_text,
                    inline_token_index=unit.inline_token_index,
                    placeholders=unit.placeholders,
                    metadata=unit.metadata,
                )
            )

        return translated_units
