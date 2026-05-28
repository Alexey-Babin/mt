"""Парсер, который разбирает форматированный markdown в синтаксическое дерево"""

# Импорт необходимых библиотек для парсинга Markdown
from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.attrs import attrs_plugin
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.field_list import fieldlist_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.tasklists import tasklists_plugin


def create_markdown_parser() -> MarkdownIt:
    """Создает и настраивает парсер Markdown с поддержкой расширенного синтаксиса."""
    md = MarkdownIt("commonmark")

    # Встроенные плагины
    md.enable("table")

    # Внешние плагины из экосистемы mdit-py
    md.use(footnote_plugin)
    md.use(tasklists_plugin)
    md.use(deflist_plugin)
    md.use(dollarmath_plugin, enable_dollars=True)
    md.use(front_matter_plugin)
    md.use(attrs_plugin)
    md.use(anchors_plugin)
    md.use(fieldlist_plugin)

    return md
