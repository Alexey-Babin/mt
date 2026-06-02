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

        # Получаем текущий префикс вложенности (например, "> " для цитат)
        prefix, _ = self._state_machine.get_current_prefix(for_block_start=False)

        # 1. Пишем открывающий маркер fence с префиксом
        if prefix and (not self._writer.buffer or self._writer.ends_with_newline()):
            self._writer.write_raw(prefix)

        info_str = unit.info or ""
        code_lines = unit.original_text.rstrip("\n").split("\n")

        # Если есть префикс вложенности (например, мы в цитате),
        # добавляем его к КАЖДОЙ строке кода, включая маркеры fence
        if prefix:
            lines_with_prefix = [f"{prefix}```{info_str}\n"]
            for line in code_lines:
                lines_with_prefix.append(f"{prefix}{line}\n")
            lines_with_prefix.append(f"{prefix}```\n\n")
            code_content = "".join(lines_with_prefix)
        else:
            code_content = f"```{info_str}\n{unit.original_text}```\n\n"

        self._writer.write_raw(f"```{info_str}\n")

        # 2. Пишем содержимое кода, добавляя префикс к каждой строке
        code_content = unit.original_text.rstrip("\n")
        code_lines = code_content.split("\n")
        for line in code_lines:
            if prefix:
                self._writer.write_raw(f"{prefix}{line}\n")
            else:
                self._writer.write_raw(f"{line}\n")

        # 3. Пишем закрывающий маркер fence с префиксом
        if prefix:
            self._writer.write_raw(f"{prefix}```\n")
        else:
            self._writer.write_raw("```\n")

        self._writer.write_raw("\n")

    def handle_hr(self):
        """Обрабатывает горизонтальный разделитель."""
        logger.debug("  Writing horizontal rule")
        self._writer.write_with_prefix("---\n\n")
