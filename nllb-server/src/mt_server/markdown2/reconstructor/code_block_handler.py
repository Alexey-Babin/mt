"""Модуль обработки блоков кода.

Отвечает за:
- Обработку fence и code_block
- Сохранение чистоты содержимого кода без префиксов вложенности
- Правильное размещение маркеров открытия/закрытия блоков кода
"""

import logging

from ..translation_unit import TranslationUnit
from .block_writer import BlockWriter
from .state_machine import StateMachine

logger = logging.getLogger("uvicorn.error")


class CodeBlockHandler:
    """Обрабатывает блоки кода (fence, code_block)."""

    def __init__(self, writer: BlockWriter, state_machine: StateMachine):
        self._writer = writer
        self._state_machine = state_machine

    def handle_fence(self, unit: TranslationUnit):
        """Обрабатывает блок кода (fence или code_block).

        Хронологический перехват блоков кода и разделителей (hr).
        Обрабатываем их строго ОДИН раз (при открытии или если это одиночный токен).
        """
        logger.debug("  Writing code block: info_str=%s", unit.info or "")

        # 1. Перед блоком кода выставляем текущий префикс вложенности (> ),
        # чтобы сам маркер открытия ``` встал на правильный уровень структуры цитаты
        prefix, _ = self._state_machine.get_current_prefix(for_block_start=False)
        if prefix and (not self._writer.buffer or self._writer.ends_with_newline()):
            self._writer.write_raw(prefix)

        # 2. Пишем сам блок кода НАПРЯМУЮ в буфер.
        # Это гарантирует, что внутренние строки кода останутся чистыми и без префиксов '> '.
        info_str = unit.info or ""
        code_content = f"```{info_str}\n{unit.original_text}```\n\n"
        self._writer.write_raw(code_content)

    def handle_hr(self):
        """Обрабатывает горизонтальный разделитель."""
        logger.debug("  Writing horizontal rule")
        self._writer.write_with_prefix("---\n\n")
