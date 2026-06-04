"""Интеграционные тесты для markdown2.

Использует фикстуры из conftest.py.
"""

import pytest


def test_markdown_translator_full_pipeline(mock_translator):
    """Сквозной интеграционный тест полного цикла перевода сложного Markdown документа.

    Проверяет, что при переводе файла с определённой структурой (заголовки, списки,
    таблицы, task lists, код в цитатах, списки определений), структура сохраняется,
    а контент переводится. Используется mock-движок с полным словарём переводов.

    Тест проверяет ПОЛНОЕ совпадение результата с ожидаемым Markdown.
    """

    # 1. Формируем исходный Markdown-текст на английском со всеми edge-cases
    source_markdown = (
        "---\n"
        "title: Document\n"
        "layout: post\n"
        "---\n\n"
        "## Some text before.\n\n"
        "This is **bold** text. Go to [Google](https://google.com).\n\n"
        "- Item 1\n"
        "    - Nested Item 1.1\n\n"
        "Term text\n"
        ": Definition text\n\n"
        "> ```python\n"
        "> def hello():\n"
        ">     print('world')\n"
        "> ```\n\n"
        "| Name | Age |\n"
        "|------|-----|\n"
        "| John | 30  |\n"
        "| Jane | 25  |\n\n"
        "- [x] Done task\n"
        "- [ ] Pending task\n\n"
        "Some text after."
    )

    # 2. Ожидаемый результат после перевода (структура сохранена, контент переведён)
    # Это ТО, ЧТО ДОЛЖНО ПОЛУЧИТЬСЯ при корректной работе системы
    expected_markdown = (
        "---\n"
        "title: Document\n"
        "layout: post\n"
        "---\n\n"
        "## Некоторый текст перед.\n\n"
        "Это **жирный** текст. Перейдите на [Google](https://google.com).\n\n"
        "- Элемент 1\n"
        "    - Вложенный элемент 1.1\n\n"
        "Текст термина\n"
        ": Текст определения\n\n"
        "> ```python\n"
        "> def hello():\n"
        ">     print('world')\n"
        "> ```\n\n"
        "| Имя | Возраст |\n"
        "|------|------|\n"
        "| Джон | 30 |\n"
        "| Джейн | 25 |\n\n"
        "- [x] Выполненная задача\n"
        "- [ ] Ожидающая задача\n\n"
        "Некоторый текст после.\n\n"
    )
    # 3. Создаем переводчик для конкретного текста и прогоняем через главный метод оркестратора
    # Используем фикстуру mock_translator из conftest.py, которая принимает text
    translator = mock_translator(source_markdown)
    result_markdown = translator.process()

    # 4. Проверяем ПОЛНОЕ совпадение с ожидаемым результатом
    # Тест будет падать, пока не исправлены баги в reconstructor.py и ast_walker.py
    assert result_markdown == expected_markdown, (
        f"Результат перевода не совпадает с ожидаемым.\n\n"
        f"=== ОЖИДАЕМЫЙ ({len(expected_markdown)} символов) ===\n{expected_markdown}\n\n"
        f"=== ПОЛУЧЕНЫЙ ({len(result_markdown)} символов) ===\n{result_markdown}\n\n"
        f"=== РАЗНИЦА (посимвольно) ===\n"
        f"Длина ожидаемого: {len(expected_markdown)}, длина полученного: {len(result_markdown)}\n"
    )


@pytest.mark.parametrize("empty_input", ["", "   ", "\n\n"])
def test_markdown_translator_handles_empty_inputs(mock_translator, empty_input):
    """Интеграционный тест: пустые строки должны мгновенно возвращать пустую строку."""
    translator = mock_translator(empty_input)
    assert translator.process() == ""
