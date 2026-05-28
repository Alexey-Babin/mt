# markdown_translator.py
"""Главный файл модуля, точка входа"""

from typing import List

from markdown_it.tree import SyntaxTreeNode

from mt_server.config import settings
from mt_server.engine import TranslationEngineProtocol as TranslationEngine

from .ast_walker import ASTWalker
from .parser import create_markdown_parser
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

        # Сюда придут новые компоненты Chunker и Reconstructor
        self.chunker = None  # Будет: MarkdownChunker(...)
        self.reconstructor = None  # Будет: MarkdownReconstructor(...)

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
        # (Передаем токенизатор, язык и лимит токенов)
        # TODO: self.chunker = MarkdownChunker(self.tokenizer, self.src_lang, self.max_tokens)
        # chunks = self.chunker.create_chunks(self.units)

        # Шаг 4: Отправляем PlainText каждого чанка в Translation Engine
        # translated_chunks_text = []
        # for chunk in chunks:
        #     plain_text_to_translate = chunk.to_plain_text()
        #
        #     # Вызов вашего движка перевода (TranslationEngineProtocol.translate)
        #     translated_plain = self.engine.translate(
        #         text=plain_text_to_translate,
        #         src_lang=self.src_lang,
        #         tgt_lang=self.tgt_lang
        #     )
        #     translated_chunks_text.append(translated_plain)

        # Шаг 5: Текст на основании плейсхолдеров раскладывается обратно в юниты
        # self.chunker.merge_translations(chunks, translated_chunks_text, self.units)

        # Шаг 6: Из плоского списка сбалансированных юнитов формируется итоговый Markdown
        # TODO: self.reconstructor = MarkdownReconstructor()
        # self.translated_text = self.reconstructor.reconstruct(self.units)

        # Фолбек-заглушка, пока не написаны Chunker и Reconstructor:
        self.translated_text = (
            "[Конвейер собран. Ожидает интеграции Chunker и Reconstructor]"
        )

        return self.translated_text
