from __future__ import annotations

import logging
from typing import Optional

from .engine import TranslatorProtocol
from .format_detection import TextFormat, looks_like_markdown

logger = logging.getLogger("uvicorn.error")


class TranslationService:
    """Служба перевода - определение формата входных данных, выбор специализированного переводчика"""

    def __init__(self, engine: TranslatorProtocol):
        self.engine = engine

    def translate(
        self,
        text: str,
        src_lang: str,
        tgt_lang: str,
        format: Optional[TextFormat] = TextFormat.AUTO,
    ) -> str:

        if not text.strip():
            return text

        if format == TextFormat.AUTO or not format:
            actual_format = self._resolve_format(
                text=text,
                format=format,
            )
            logger.info(
                f"Detected format: {actual_format.value} for translation {src_lang}->{tgt_lang}"
            )
        else:
            actual_format = format
            logger.info(
                f"Using format: {actual_format.value} for translation {src_lang}->{tgt_lang}"
            )
        try:
            match actual_format:
                case TextFormat.MARKDOWN:
                    # TODO: Develop and create markdown translator
                    raise NotImplementedError("Markdown is not implemented yet")

                case _:
                    return self.engine.translate(
                        text,
                        src_lang,
                        tgt_lang,
                    )
        except Exception as e:
            logger.error(f"Translation service error: {e}", exc_info=True)
            # Fallback: пробуем перевести как plain text, чтобы не возвращать ошибку пользователю
            if actual_format == TextFormat.MARKDOWN:
                logger.warning(
                    "Falling back to plain text translation due to Markdown processing error."
                )
                return self.engine.translate(text, src_lang, tgt_lang)
            raise

    @staticmethod
    def _resolve_format(
        text: str,
        format: Optional[TextFormat],
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
