from __future__ import annotations

import logging
import re
import shutil

import pypandoc

from mt_server.markdown.extractor import MarkdownTranslationUnitExtractor
from mt_server.markdown.units import TranslationUnit

FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
logger = logging.getLogger("uvicorn.error")


class MarkdownTranslator:
    def __init__(self, translator):
        self.translator = translator
        self.extractor = MarkdownTranslationUnitExtractor()

        self.pandoc_available = shutil.which("pandoc") is not None
        if not self.pandoc_available:
            logger.warning("Pandoc not found — fallback to HTML output")

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        frontmatter = ""

        match = FRONTMATTER_RE.match(text)
        if match:
            frontmatter = match.group(0)
            body = text[len(match.group(0)) :]
        else:
            body = text

        tokens, units = self.extractor.extract(body)

        if not units:
            return text

        translated_units = self._translate_units(units, src_lang, tgt_lang)
        self._apply_translations(tokens, translated_units)

        html = self._render_html(tokens)
        translated_body = self._html_to_markdown(html).lstrip("\n")

        if frontmatter:
            return frontmatter + translated_body

        return translated_body

    def _translate_units(
        self,
        units: list[TranslationUnit],
        src_lang: str,
        tgt_lang: str,
    ) -> list[TranslationUnit]:

        result: list[TranslationUnit] = []

        for unit in units:
            translated_text = self.translator.translate(
                text=unit.text,
                src_lang=src_lang,
                tgt_lang=tgt_lang,
            )

            result.append(
                TranslationUnit(
                    id=unit.id,
                    type=unit.type,
                    text=translated_text,
                    inline_token_index=unit.inline_token_index,
                    placeholders=unit.placeholders,
                    metadata=unit.metadata,
                )
            )

        return result

    @staticmethod
    def _apply_translations(tokens: list, units: list[TranslationUnit]) -> None:
        mapping = {u.inline_token_index: u.text for u in units}

        for i, token in enumerate(tokens):
            if token.type == "inline" and i in mapping:
                token.content = mapping[i]

    def _render_html(self, tokens: list) -> str:
        from markdown_it import MarkdownIt

        md = MarkdownIt("commonmark", {"html": False})
        return md.renderer.render(tokens, md.options, {})

    def _html_to_markdown(self, html: str) -> str:
        """
        Pandoc fallback strategy:
        - if pandoc exists → good markdown
        - if not → return HTML (safe fallback)
        """

        if self.pandoc_available:
            try:
                return pypandoc.convert_text(
                    html,
                    to="markdown",
                    format="html",
                )
            except Exception as e:
                logger.warning(f"Pandoc failed, fallback to HTML: {e}")
                return html

        return html
