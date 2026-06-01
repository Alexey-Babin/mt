"""Модуль записи блоков с префиксами и форматированием.

Отвечает за:
- Запись текста в буфер с правильными префиксами вложенности
- Обработку многострочного текста с сохранением отступов
- Форматирование завершающих переносов строк
"""

import logging
from typing import List

logger = logging.getLogger("uvicorn.error")


class BlockWriter:
    """Записывает текст в буфер с учетом префиксов вложенности."""

    def __init__(self, get_prefix_callback):
        """Инициализирует писатель блоков.

        Args:
            get_prefix_callback: Функция для получения префикса (line_prefix, item_marker)
        """
        self._buffer: List[str] = []
        self._get_prefix = get_prefix_callback

    @property
    def buffer(self) -> List[str]:
        """Возвращает текущий буфер."""
        return self._buffer

    def reset(self):
        """Очищает буфер."""
        self._buffer = []

    def get_buffer_content(self) -> str:
        """Возвращает содержимое буфера как строку."""
        return "".join(self._buffer)

    def write_with_prefix(self, text: str):
        """Записывает текст в буфер, динамически рассчитывая отступы списков и цитат."""
        # Получаем префиксы для СТАРТА блока текста (первой строки)
        line_prefix, item_marker = self._get_prefix(for_block_start=True)

        # Сборка стартовой строки с учетом маркера списка (если он есть)
        start_prefix = line_prefix + item_marker

        if not self._buffer or self._buffer[-1].endswith("\n"):
            self._buffer.append(start_prefix)

        # Для последующих строк (если текст многострочный) маркер списка не нужен,
        # используются только стандартные отступы line_prefix
        multi_prefix, _ = self._get_prefix(for_block_start=False)

        # Модифицируем внутренние переносы строк
        processed_text = text.replace("\n", f"\n{multi_prefix}")

        if processed_text.endswith(f"\n{multi_prefix}"):
            processed_text = processed_text[: -len(multi_prefix)]

        self._buffer.append(processed_text)

    def write_raw(self, text: str):
        """Записывает текст напрямую в буфер без префиксов."""
        self._buffer.append(text)

    def ensure_newline(self):
        """Гарантирует, что буфер заканчивается переносом строки."""
        if self._buffer and not self._buffer[-1].endswith("\n"):
            self._buffer.append("\n")

    def ensure_double_newline(self):
        """Гарантирует, что буфер заканчивается двойным переносом строки."""
        self.ensure_newline()
        if len(self._buffer) < 2 or not self._buffer[-2].endswith("\n"):
            self._buffer.append("\n")

    def ends_with_newline(self) -> bool:
        """Проверяет, заканчивается ли буфер переносом строки."""
        return bool(self._buffer) and self._buffer[-1].endswith("\n")

    def contains_pipe(self) -> bool:
        """Проверяет, содержит ли буфер символ | (для таблиц)."""
        return "|" in self.get_buffer_content()

    def get_last_pipe_line(self) -> str:
        """Получает последнюю строку с символом |."""
        lines = self.get_buffer_content().split("\n")
        for line in reversed(lines):
            if "|" in line and line.strip():
                return line
        return ""

    def count_table_columns(self) -> int:
        """Подсчитывает количество столбцов в таблице по последней строке с |."""
        last_pipe_line = self.get_last_pipe_line()
        if last_pipe_line:
            return last_pipe_line.count("|") - 1
        return 0
