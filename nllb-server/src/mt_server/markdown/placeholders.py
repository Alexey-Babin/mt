# src/mt_server/markdown/placeholders.py

import logging
from typing import Callable

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

logger = logging.getLogger(__name__)


def translate_html_content(
    html_fragment: str, translate_fn: Callable[[str], str]
) -> str:
    """
    Переводит текстовое содержимое HTML-фрагмента, сохраняя все теги и атрибуты.

    Стратегия:
    1. Парсим фрагмент в DOM (BeautifulSoup).
    2. Рекурсивно обходим узлы.
    3. Если узел - текст (NavigableString) и не внутри <code>, <pre>, <script> -> переводим.
    4. Если узел - тег -> пропускаем сам тег, рекурсивно обрабатываем детей.

    Args:
        html_fragment: Строка с HTML (например, содержимое одного <p>...</p>).
        translate_fn: Функция перевода текста (str -> str).

    Returns:
        HTML-строка с переведенным текстом и сохраненной структурой.
    """
    if not html_fragment.strip():
        return html_fragment

    try:
        # 'html.parser' встроен в Python, не требует внешних зависимостей кроме bs4
        soup = BeautifulSoup(html_fragment, "html.parser")
    except Exception as e:
        logger.error(f"Failed to parse HTML fragment: {e}. Returning original.")
        return html_fragment

    def _process_node(node):
        # Игнорируем блоки кода и скрипты полностью
        if isinstance(node, Tag) and node.name in [
            "code",
            "pre",
            "script",
            "style",
            "kbd",
        ]:
            return

        if isinstance(node, NavigableString):
            text = str(node).strip()
            if not text:
                return

            # Не переводим, если это просто пробелы между тегами
            parent = node.parent
            if parent and parent.name in ["code", "pre", "script"]:
                return

            # Вызов перевода
            try:
                translated = translate_fn(text)
                node.replace_with(translated)
            except Exception as e:
                logger.error(f"Translation failed for segment '{text[:50]}...': {e}")
                # При ошибке оставляем оригинал
                pass

        elif isinstance(node, Tag):
            # Рекурсивно обрабатываем детей тега
            for child in list(node.children):
                _process_node(child)

    _process_node(soup)

    # Возвращаем HTML без оберточного документа (decode_contents vs str(soup))
    return str(soup.decode_contents())
