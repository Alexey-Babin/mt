# translator.py
"""Оркестратор конвейера перевода Markdown-документов."""

import logging
from typing import List, Optional

from markdown_it.tree import SyntaxTreeNode

from mt_server.config import settings
from mt_server.engine import TranslationEngineProtocol as TranslationEngine

from .ast_walker import ASTWalker
from .chunker import MarkdownChunk, MarkdownChunker
from .models.translation_unit import TranslationUnit
from .parser import create_markdown_parser
from .reconstructor import MarkdownReconstructor

logger = logging.getLogger("uvicorn.error")


class MarkdownTranslator:
    """Точка входа. Управляет полным конвейером перевода Markdown-документа.
    Создается для каждого отдельного текста, изолируя состояние перевода.
    """

    def __init__(
        self,
        text: str,
        src_lang: str,
        tgt_lang: str,
        engine: TranslationEngine,
        max_tokens: Optional[int] = None,
    ):
        self.text = text
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.engine = engine
        self.tokenizer = self.engine.tokenizer

        self.parser = create_markdown_parser()
        self.walker = ASTWalker()

        self.chunker = MarkdownChunker(
            tokenizer=self.tokenizer,
            max_tokens=max_tokens if max_tokens is not None else settings.max_input_tokens,
            nllb_lang_code=self.src_lang,
        )
        self.reconstructor = MarkdownReconstructor()

        self.units: List[TranslationUnit] = []
        self.translated_text: str = ""

    def process(self) -> str:
        """Главный метод конвейера (вызывается пользователем)."""
        if not self.text.strip():
            return ""

        logger.info("Starting Markdown translation pipeline")
        logger.debug("Input text length: %d characters", len(self.text))

        # Шаг 1: Формируем синтаксическое дерево (AST)
        tokens = self.parser.parse(self.text)
        ast_root = SyntaxTreeNode(tokens)

        logger.debug(
            "AST parsed: root type=%s, children count=%d",
            ast_root.type,
            len(ast_root.children) if ast_root.children else 0,
        )

        # Шаг 2: Разбираем текст на TranslationUnit (сохраняя структуру стеком)
        self.units = self.walker.walk(ast_root)

        translatable_count = sum(1 for u in self.units if u.need_translation)
        logger.info(
            "AST walked: total units=%d, translatable units=%d",
            len(self.units),
            translatable_count,
        )

        # Шаг 3: Нарезаем переводимые юниты на безопасные чанки для NLLB
        chunks = self.chunker.create_chunks(self.units)
        total_tokens = sum(c.token_count for c in chunks)
        logger.info(
            "Chunks created: count=%d, total tokens=%d", len(chunks), total_tokens
        )

        # Шаг 4: Отправляем каждый чанк в Translation Engine
        translated_chunks_text = self._translate_chunks(chunks)

        # Шаг 5: Текст на основании плейсхолдеров раскладывается обратно в юниты
        self.chunker.merge_translations(chunks, translated_chunks_text, self.units)

        translated_units = sum(1 for u in self.units if u.is_translated)
        errors_count = sum(1 for u in self.units if u.has_errors)
        logger.info(
            "Translations merged: translated units=%d, errors=%d",
            translated_units,
            errors_count,
        )

        # Шаг 6: Из плоского списка сбалансированных юнитов формируется итоговый Markdown
        self.translated_text = self.reconstructor.reconstruct(self.units)

        logger.info(
            "Reconstruction complete: output length=%d characters",
            len(self.translated_text),
        )
        logger.info("Markdown translation pipeline completed successfully")

        return self.translated_text

    def _translate_chunks(self, chunks: List[MarkdownChunk]) -> List[str]:
        """Переводит каждый чанк через engine и возвращает список переведённых текстов."""
        translated: List[str] = []
        for i, chunk in enumerate(chunks):
            plain_text = chunk.to_plain_text()

            logger.debug(
                "Translating chunk %d/%d: %d tokens, %d segments",
                i + 1,
                len(chunks),
                chunk.token_count,
                len(chunk.segments),
            )

            result = self.engine.translate(
                text=plain_text,
                src_lang=self.src_lang,
                tgt_lang=self.tgt_lang,
            )
            translated.append(result)

            logger.debug(
                "Chunk %d translated: response length=%d characters",
                i + 1,
                len(result),
            )
        return translated
