"""Модуль для восстановления Markdown-документа из TranslationUnit.

Этот модуль декомпозирует сложную логику MarkdownReconstructor на отдельные компоненты:
- StateMachine: управление состоянием и стеком блоков
- BlockWriter: запись блоков с префиксами и отступами
- PlaceholderRestorer: восстановление плейсхолдеров в инлайн-разметке
- TableHandler: обработка табличной разметки
- CodeBlockHandler: обработка блоков кода
"""

from .block_writer import BlockWriter
from .code_block_handler import CodeBlockHandler

# Импортируем главный класс из main.py
from .main import MarkdownReconstructor
from .placeholder_restorer import PlaceholderRestorer
from .state_machine import StateMachine
from .table_handler import TableHandler

__all__ = [
    "StateMachine",
    "BlockWriter",
    "PlaceholderRestorer",
    "TableHandler",
    "CodeBlockHandler",
    "MarkdownReconstructor",
]
