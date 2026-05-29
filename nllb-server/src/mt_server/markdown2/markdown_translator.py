# markdown_translator.py
"""Главный файл модуля, точка входа"""

from typing import List

from markdown_it.tree import SyntaxTreeNode

from mt_server.config import settings
from mt_server.engine import TranslationEngineProtocol as TranslationEngine

from .ast_walker import ASTWalker
from .chunker import MarkdownChunker
from .parser import create_markdown_parser  # Изменено под имя вашего файла
from .reconstructor import MarkdownReconstructor
from .translation_unit import TranslationUnit

max_input_tokens = settings.max_input_tokens


class MarkdownTranslator:
    """Точка входа. Управляет полным конвейером перевода Markdown-документа.
    Создается для каждого отдельного текста, изолируя состояние перевода.
    """

    def __init__(
        self, translation_engine: TranslationEngine, src_lang: str, tgt_lang: str
    ):
        self.engine = translation_engine
        self.tokenizer = self.engine.tokenizer
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang

        # Инициализируем компоненты архитектуры
        self.parser = create_markdown_parser()
        self.walker = ASTWalker()

        # Инжектируем Chunker и Reconstructor в соответствии с их точным контрактом API
        self.chunker = MarkdownChunker(
            tokenizer=self.tokenizer,
            max_tokens=max_input_tokens,
            nllb_lang_code=self.src_lang,
        )
        self.reconstructor = MarkdownReconstructor()

        # Внутреннее состояние текущего сеанса перевода
        self.source_text: str = ""
        self.translated_text: str = ""
        self.units: List[TranslationUnit] = []

    def process(self, markdown_text: str) -> str:
        """Главный метод конвейера (вызывается пользователем)."""
        if not markdown_text.strip():
            return ""

        self.source_text = markdown_text

        # Шаг 1: Формируем синтаксическое дерево (AST)
        tokens = self.parser.parse(self.source_text)
        ast_root = SyntaxTreeNode(tokens)

        # Шаг 2: Разбираем текст на TranslationUnit (сохраняя структуру стеком)
        self.units = self.walker.walk(ast_root)

        # Шаг 3: Нарезаем переводимые юниты на безопасные чанки для NLLB
        chunks = self.chunker.create_chunks(self.units)

        # Шаг 4: Отправляем PlainText каждого чанка в Translation Engine
        translated_chunks_text = []
        for chunk in chunks:
            plain_text_to_translate = chunk.to_plain_text()

            # Вызов вашего оригинального движка перевода по протоколу TranslationEngineProtocol
            translated_plain = self.engine.translate(
                text=plain_text_to_translate,
                src_lang=self.src_lang,
                tgt_lang=self.tgt_lang,
            )
            translated_chunks_text.append(translated_plain)

        # Шаг 5: Текст на основании плейсхолдеров раскладывается обратно в юниты
        self.chunker.merge_translations(chunks, translated_chunks_text, self.units)

        # Шаг 6: Из плоского списка сбалансированных юнитов формируется итоговый Markdown
        self.translated_text = self.reconstructor.reconstruct(self.units)

        return self.translated_text
