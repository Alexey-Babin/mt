from unittest.mock import MagicMock

import pytest

# Замените на ваши реальные пути импорта
from src.mt_server.markdown2.ast_walker import ASTWalker
from src.mt_server.markdown2.models.translation_unit_type import TranslationUnitType


@pytest.fixture
def walker():
    return ASTWalker()


def test_walk_plain_paragraph(walker):
    """Базовый тест: обычный параграф с текстом.

    Структура: paragraph_open -> inline -> text -> paragraph_close
    """
    p_open = MagicMock(type="paragraph_open", level=0, tag="p", attrs={})
    p_close = MagicMock(type="paragraph_close", level=0, tag="p", attrs={})

    inline_node = MagicMock(type="inline")
    text_node = MagicMock(type="text", content="Привет мир")

    # Настраиваем связи (children)
    p_open.children = [inline_node]
    p_close.children = []
    inline_node.children = [text_node]
    text_node.children = []

    # Имитируем корневой документ, который содержит эти токены
    root = MagicMock(type="document")
    root.children = [p_open, p_close]

    units = walker.walk(root)

    # Должно быть 2 юнита: сам собранный параграф и закрывающий маркер-маяк
    assert len(units) == 2

    p_unit = units[0]
    assert p_unit.node_type == "paragraph"
    assert p_unit.unit_type == TranslationUnitType.CONTEXT_BLOCK
    assert p_unit.need_translation is True
    assert p_unit.original_text == "Привет мир"
    assert p_unit.extracted_text == "Привет мир"

    close_unit = units[1]
    assert close_unit.node_type == "paragraph_close"
    assert close_unit.need_translation is False


def test_walk_paragraph_with_inline_formatting(walker):
    """Тест параграфа с инлайн-форматированием (жирный текст).

    Структура: paragraph_open -> inline -> text -> strong_open -> text -> strong_close -> paragraph_close
    """
    p_open = MagicMock(type="paragraph_open", level=0, tag="p", attrs={})
    p_close = MagicMock(type="paragraph_close", level=0, tag="p", attrs={})

    inline_node = MagicMock(type="inline")
    text1 = MagicMock(type="text", content="Это ")
    strong_open = MagicMock(type="strong_open", markup="**")
    text2 = MagicMock(type="text", content="важно")
    strong_close = MagicMock(type="strong_close", markup="**")

    p_open.children = [inline_node]
    inline_node.children = [text1, strong_open, strong_close]
    strong_open.children = [text2]  # Текст "важно" сидит внутри strong в SyntaxTreeNode
    strong_close.children = []

    root = MagicMock(type="document")
    root.children = [p_open, p_close]

    units = walker.walk(root)
    p_unit = units[0]

    assert p_unit.original_text == "Это **важно"
    # Маска должна быть в dunder-формате (__B_O_1__ ... __B_C_1__) с пробелами вокруг
    assert p_unit.extracted_text == "Это __B_O_1__ важно __B_C_1__ "
    assert len(p_unit.placeholders) == 2  # strong_open и strong_close


def test_walk_nested_structural_blocks(walker):
    """Сложный тест-кейс: Вложенные блочные структуры (Заголовок внутри цитаты).

    Синтаксис:
    > ## Заголовок

    Структура: blockquote_open -> heading_open -> inline -> text -> heading_close -> blockquote_close
    """
    bq_open = MagicMock(type="blockquote_open", tag="blockquote", level=0, attrs={})
    bq_close = MagicMock(type="blockquote_close", tag="blockquote", level=0, attrs={})

    h_open = MagicMock(type="heading_open", tag="h2", level=1, attrs={})
    h_close = MagicMock(type="heading_close", tag="h2", level=1, attrs={})

    inline_node = MagicMock(type="inline")
    text_node = MagicMock(type="text", content="Заголовок")

    # Выстраиваем иерархию вложенности
    bq_open.children = [h_open, h_close]
    h_open.children = [inline_node]
    inline_node.children = [text_node]

    root = MagicMock(type="document")
    root.children = [bq_open, bq_close]

    units = walker.walk(root)

    # Ожидаем 4 юнита, сохраняющих идеальный баланс тегов для реструктуризатора:
    # 1. blockquote_open (маркер каркаса)
    # 2. heading (блок с контентом для перевода)
    # 3. heading_close (маркер каркаса)
    # 4. blockquote_close (маркер каркаса)
    assert len(units) == 4

    assert units[0].node_type == "blockquote_open"
    assert units[0].need_translation is False

    assert units[1].node_type == "heading"
    assert units[1].unit_type == TranslationUnitType.CONTEXT_BLOCK
    assert units[1].need_translation is True
    assert units[1].original_text == "Заголовок"

    assert units[2].node_type == "heading_close"
    assert units[2].need_translation is False

    assert units[3].node_type == "blockquote_close"
    assert units[3].need_translation is False


def test_walk_front_matter_special_case(walker):
    """Тест изоляции метаданных Front Matter."""
    fm_node = MagicMock(type="front_matter", content="title: Тест\nlayout: post")
    fm_node.children = []

    root = MagicMock(type="document")
    root.children = [fm_node]

    units = walker.walk(root)

    assert len(units) == 1
    fm_unit = units[0]
    assert fm_unit.unit_type == TranslationUnitType.SPECIAL_CASE
    assert fm_unit.need_translation is False
    assert fm_unit.original_text == "title: Тест\nlayout: post"


def test_walk_nested_multiple_context_blocks_in_structural_node(walker):
    """Тест глубокой вложенности: Цитирование, содержащее абзац, а затем заголовок.

    Синтаксис Markdown:
    > Это абзац.
    > ## Это заголовок

    Структура дерева AST:
    blockquote_open
      ├── paragraph_open -> inline -> text("Это абзац.") -> paragraph_close
      └── heading_open   -> inline -> text("Это заголовок") -> heading_close
    blockquote_close
    """
    bq_open = MagicMock(type="blockquote_open", tag="blockquote", level=0, attrs={})
    bq_close = MagicMock(type="blockquote_close", tag="blockquote", level=0, attrs={})

    # 1. Первый блок внутри цитаты — параграф
    p_open = MagicMock(type="paragraph_open", tag="p", level=1, attrs={})
    p_close = MagicMock(type="paragraph_close", tag="p", level=1, attrs={})
    p_inline = MagicMock(type="inline")
    p_text = MagicMock(type="text", content="Это абзац.")

    p_open.children = [p_inline]
    p_inline.children = [p_text]
    p_text.children = []
    p_close.children = []

    # 2. Второй блок внутри цитаты — заголовок
    h_open = MagicMock(type="heading_open", tag="h2", level=1, attrs={})
    h_close = MagicMock(type="heading_close", tag="h2", level=1, attrs={})
    h_inline = MagicMock(type="inline")
    h_text = MagicMock(type="text", content="Это заголовок")

    h_open.children = [h_inline]
    h_inline.children = [h_text]
    h_text.children = []
    h_close.children = []

    # Собираем дерево цитаты
    bq_open.children = [p_open, p_close, h_open, h_close]
    bq_close.children = []

    # Корневой документ
    root = MagicMock(type="document")
    root.children = [bq_open, bq_close]

    units = walker.walk(root)

    # Ожидаем строго упорядоченный список из 6 юнитов (DFS хронология):
    # 1. blockquote_open  (need_translation=False)
    # 2. paragraph        (need_translation=True)
    # 3. paragraph_close  (need_translation=False)
    # 4. heading          (need_translation=True)
    # 5. heading_close    (need_translation=False)
    # 6. blockquote_close (need_translation=False)
    assert len(units) == 6

    assert units[0].node_type == "blockquote_open"
    assert units[0].need_translation is False

    assert units[1].node_type == "paragraph"
    assert units[1].need_translation is True
    assert units[1].extracted_text == "Это абзац."

    assert units[2].node_type == "paragraph_close"
    assert units[2].need_translation is False

    assert units[3].node_type == "heading"
    assert units[3].need_translation is True
    assert units[3].extracted_text == "Это заголовок"

    assert units[4].node_type == "heading_close"
    assert units[4].need_translation is False

    assert units[5].node_type == "blockquote_close"
    assert units[5].need_translation is False


def test_walk_structural_ignore_inside_context_is_not_intercepted_as_block(walker):
    """Тест вашего исправления: STRUCTURAL_IGNORE узлы (например, 'inline') внутри CONTEXT_BLOCK
    должны корректно перенаправляться в _collect_inline, а не обрабатываться как блоки верхнего уровня.
    """
    p_open = MagicMock(type="paragraph_open", level=0, tag="p", attrs={})
    p_close = MagicMock(type="paragraph_close", level=0, tag="p", attrs={})

    # inline-узел имеет тип STRUCTURAL_IGNORE в node_type.py.
    # Мы проверяем, что при активном стеке он уходит в инлайны, а не сбрасывает стек.
    inline_node = MagicMock(type="inline")
    text_node = MagicMock(type="text", content="Проверка перенаправления")

    p_open.children = [inline_node]
    inline_node.children = [text_node]
    text_node.children = []
    p_close.children = []

    root = MagicMock(type="document")
    root.children = [p_open, p_close]

    units = walker.walk(root)

    # Если бы исправление не работало, узел inline сломал бы логику накопления контекста.
    # При правильной работе мы получаем ровно 2 юнита.
    assert len(units) == 2
    assert units[0].node_type == "paragraph"
    assert units[0].extracted_text == "Проверка перенаправления"
    assert units[1].node_type == "paragraph_close"
