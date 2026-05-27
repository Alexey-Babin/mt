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
    """Обработчик для plain text формата. Передает текст напрямую в движок перевода."""

    def handle(
        self, text: str, src_lang: str, tgt_lang: str, engine: TranslationEngineProtocol
    ) -> str:
        return engine.translate(text, src_lang, tgt_lang)

    @property
    def supported_formats(self) -> list[TextFormat]:
        return [TextFormat.PLAIN]


class MarkdownHandler(FormatHandler):
    """Обработчик для Markdown формата. Пока не реализован."""

    def handle(
        self, text: str, src_lang: str, tgt_lang: str, engine: TranslationEngineProtocol
    ) -> str:
        raise NotImplementedError("Markdown is not implemented yet")

    @property
    def supported_formats(self) -> list[TextFormat]:
        return [TextFormat.MARKDOWN]
