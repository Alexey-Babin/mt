"""Модуль обработки табличной разметки.

Отвечает за:
- Обработку ячеек таблицы (th, td)
- Генерацию разделительных строк между thead и tbody
- Управление переносами строк в строках таблицы
"""

import logging

from ..translation_unit import TranslationUnit
from .block_writer import BlockWriter
from .state_machine import StateMachine

logger = logging.getLogger("uvicorn.error")


class TableHandler:
    """Обрабатывает табличную разметку Markdown."""

    def __init__(self, writer: BlockWriter, state_machine: StateMachine):
        self._writer = writer
        self._state_machine = state_machine

    def handle_cell_open(self, unit: TranslationUnit):
        """Обрабатывает открытие ячейки таблицы (th/td).
        Добавляет | перед содержимым ячейки.
        """
        # Добавляем | и пробел для правильного форматирования таблицы
        self._writer.write_raw("| ")

    def handle_cell_close(self, base_type: str):
        """Обрабатывает закрытие ячейки таблицы.

        Добавляет завершающий | для ячейки.
        """
        if base_type in ("th", "td"):
            # Пробел перед | для правильного форматирования таблицы
            self._writer.write_raw("|")

    def handle_tbody_open(self):
        """Обрабатывает открытие tbody.

        Генерирует разделительную строку после заголовков таблицы.
        """
        # Проверяем, есть ли в буфере уже содержимое таблицы (заголовки)
        if self._writer.contains_pipe() and not self._state_machine.is_inside_list():
            col_count = self._writer.count_table_columns()
            if col_count > 0:
                # Добавляем перенос строки перед разделителем, если нужно
                if not self._writer.ends_with_newline():
                    self._writer.write_raw("\n")
                separator = "|" + "|".join(["------"] * col_count) + "|\n"
                self._writer.write_raw(separator)
                logger.debug("Added table separator: %s", separator.strip())

        # Пушим флаг, что мы внутри tbody
        self._state_machine.push_block("in_tbody", is_first_line=True)

    def handle_tbody_close(self):
        """Обрабатывает закрытие tbody."""
        self._state_machine.pop_block("in_tbody")

    def handle_tr_open(self):
        """Обрабатывает открытие строки таблицы.

        Добавляет перенос строки перед началом строки, если это не первая строка.
        """
        if (
            self._writer.get_buffer_content()
            and self._writer.contains_pipe()
            and not self._writer.ends_with_newline()
        ):
            self._writer.write_raw("\n")

    def handle_tr_close(self):
        """Обрабатывает закрытие строки таблицы.

        Гарантирует перенос строки после закрытия строки.
        """
        self._writer.write_raw("\n")

    def handle_thead_open(self):
        """Обрабатывает открытие thead.

        Пока просто пропускаем - разделитель будет добавлен при открытии tbody.
        """
        pass

    def handle_table_open(self):
        """Обрабатывает открытие таблицы.

        Пока просто пропускаем - обработка идет на уровне ячеек и строк.
        """
        pass
