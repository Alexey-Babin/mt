from __future__ import annotations

from abc import ABC, abstractmethod

from .engine import TranslationEngineProtocol
from .format_detection import TextFormat


class FormatHandler(ABC):
    """Абстрактный базовый класс для обработчиков различных форматов текста."""

    @abstractmethod
    def handle(
        self, text: str, src_lang: str, tgt_lang: str, engine: TranslationEngineProtocol
    ) -> str:
        """Обработать текст с использованием указанного движка перевода.

        Args:
            text: Исходный текст для перевода.
            src_lang: Код исходного языка.
            tgt_lang: Код целевого языка.
            engine: Движок перевода для выполнения трансляции.

        Returns:
            Переведенный текст.
        """
        pass

    @property
    @abstractmethod
    def supported_formats(self) -> list[TextFormat]:
        """Возвращает список форматов, которые поддерживает данный обработчик."""
        pass


class PlainHandler(FormatHandler):
    """Обработчик для plain text формата. Использует PlainTextTranslator."""

    def handle(
        self, text: str, src_lang: str, tgt_lang: str, engine: TranslationEngineProtocol
    ) -> str:
        from .plain_text_translator import PlainTextTranslator

        translator = PlainTextTranslator(
            text=text,
            src_lang=src_lang,
            target_lang=tgt_lang,
            engine=engine,
        )
        return translator.process()

    @property
    def supported_formats(self) -> list[TextFormat]:
        return [TextFormat.PLAIN]


class MarkdownHandler(FormatHandler):
    """Обработчик для Markdown формата. Использует MarkdownTranslator."""

    def handle(
        self, text: str, src_lang: str, tgt_lang: str, engine: TranslationEngineProtocol
    ) -> str:
        from .markdown2.markdown_translator import MarkdownTranslator

        translator = MarkdownTranslator(
            text=text,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            engine=engine,
        )
        return translator.process()

    @property
    def supported_formats(self) -> list[TextFormat]:
        return [TextFormat.MARKDOWN]
