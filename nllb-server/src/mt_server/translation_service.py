from __future__ import annotations

from enum import StrEnum

from mt_server.format_detection import looks_like_markdown
from mt_server.markdown.translator import MarkdownTranslator


class TextFormat(StrEnum):
    AUTO = "auto"
    PLAIN = "plain"
    MARKDOWN = "markdown"


class TranslationService:
    def __init__(self, translator):
        self.translator = translator
        self.markdown_translator = MarkdownTranslator(translator=translator)

    def translate(
        self,
        text: str,
        src_lang: str,
        tgt_lang: str,
        format: TextFormat = TextFormat.AUTO,
    ) -> str:
        actual_format = self._resolve_format(
            text=text,
            format=format,
        )

        match actual_format:
            case TextFormat.MARKDOWN:
                return self.markdown_translator.translate(
                    text=text,
                    src_lang=src_lang,
                    tgt_lang=tgt_lang,
                )

            case _:
                return self.translator.translate(
                    text=text,
                    src_lang=src_lang,
                    tgt_lang=tgt_lang,
                )

    @staticmethod
    def _resolve_format(
        text: str,
        format: TextFormat,
    ) -> TextFormat:
        match format:
            case TextFormat.PLAIN:
                return TextFormat.PLAIN

            case TextFormat.MARKDOWN:
                return TextFormat.MARKDOWN

            case TextFormat.AUTO:
                if looks_like_markdown(text):
                    return TextFormat.MARKDOWN

                return TextFormat.PLAIN

            case _:
                return TextFormat.PLAIN
