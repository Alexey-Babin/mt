"""Тесты PlaceholderManager с новым dunder-форматом."""

from unittest.mock import MagicMock

import pytest
from src.mt_server.markdown2.models.placeholder import PlaceholderManager
from src.mt_server.markdown2.models.placeholder_codes import (
    PAIRED_CODES,
    PROTECT_CODES,
    SINGLE_TRANSLATE_CODES,
    format_placeholder,
    get_code,
)


@pytest.fixture
def manager():
    return PlaceholderManager()


def test_create_placeholder_inline_protect_code(manager):
    """Тест изоляции инлайн-кода через MagicMock."""
    node = MagicMock()
    node.type = "code_inline"
    node.content = "pip install pytest"

    ph = manager.create_placeholder(node)

    assert ph.id == 1
    assert ph.tag_mask == "__C_1__"
    assert ph.strategy == "INLINE_PROTECT"
    assert ph.original_markup == "`pip install pytest`"
    assert ph.is_closing is False
    assert "__C_1__" in manager.registry


def test_create_placeholder_inline_protect_math(manager):
    """Тест изоляции формул через MagicMock."""
    node = MagicMock()
    node.type = "math_inline"
    node.content = "E=mc^2"

    ph = manager.create_placeholder(node)

    assert ph.tag_mask == "__M_1__"
    assert ph.original_markup == "$E=mc^2$"


def test_create_placeholder_paired_tags_stack_logic(manager):
    """Тест проверки вложенности и синхронизации ID через стек (MagicMock)."""
    strong_open = MagicMock(type="strong_open", markup="**")
    em_open = MagicMock(type="em_open", markup="_")
    em_close = MagicMock(type="em_close", markup="_")
    strong_close = MagicMock(type="strong_close", markup="**")

    # 1. Открываем strong
    ph_s_open = manager.create_placeholder(strong_open)
    assert ph_s_open.tag_mask == "__B_O_1__"

    # 2. Открываем em (вложенный)
    ph_e_open = manager.create_placeholder(em_open)
    assert ph_e_open.tag_mask == "__I_O_2__"

    # 3. Закрываем em (ID=2)
    ph_e_close = manager.create_placeholder(em_close)
    assert ph_e_close.is_closing is True
    assert ph_e_close.tag_mask == "__I_C_2__"

    # 4. Закрываем strong (ID=1)
    ph_s_close = manager.create_placeholder(strong_close)
    assert ph_s_close.is_closing is True
    assert ph_s_close.tag_mask == "__B_C_1__"


def test_create_placeholder_link_attributes(manager):
    """Тест сохранения атрибутов ссылки (MagicMock)."""
    link_open = MagicMock(type="link_open", markup="[")
    link_open.attrs = {"href": "https://example.com", "title": "Example"}

    ph = manager.create_placeholder(link_open)

    assert ph.tag_mask == "__L_O_1__"
    assert ph.strategy == "INLINE_TRANSLATE"
    assert isinstance(ph.original_markup, dict)
    assert ph.original_markup["href"] == "https://example.com"
    assert ph.original_markup["title"] == "Example"

    # Закрывающий тег
    link_close = MagicMock(type="link_close", markup="]")
    ph_close = manager.create_placeholder(link_close)
    assert ph_close.is_closing is True
    assert ph_close.tag_mask == "__L_C_1__"
    assert ph_close.original_markup == ""


def test_create_placeholder_image_as_inline_translate(manager):
    """Тест обработки изображения как INLINE_TRANSLATE."""
    image = MagicMock(type="image", markup="![")
    image.attrs = {"src": "image.png", "title": "My Image"}
    image.content = "Alt text"

    ph = manager.create_placeholder(image)

    assert ph.tag_mask == "__G_1__"
    assert ph.strategy == "INLINE_TRANSLATE"
    assert isinstance(ph.original_markup, dict)
    assert ph.original_markup["src"] == "image.png"
    assert ph.original_markup["title"] == "My Image"


def test_edge_case_unbalanced_closing_tag(manager):
    """Тест несбалансированного закрывающего тега (fallback)."""
    # Закрываем strong без открытия
    strong_close = MagicMock(type="strong_close", markup="**")
    ph = manager.create_placeholder(strong_close)

    # Должен создать новый ID
    assert ph.is_closing is True
    assert ph.tag_mask == "__B_C_1__"


def test_edge_case_unknown_node_type_fallback(manager):
    """Тест неизвестного типа узла (fallback)."""
    unknown = MagicMock(type="unknown_type", markup="?")
    unknown.content = "some content"

    ph = manager.create_placeholder(unknown)

    # Должен использовать fallback (первая буква типа)
    assert ph.tag_mask == "__U_1__"
    assert ph.original_markup == "some content"


def test_placeholder_codes_completeness():
    """Тест полноты словаря кодов плейсхолдеров."""
    # Проверяем, что все ожидаемые типы есть в словаре
    expected_paired = {"strong", "em", "s", "link"}
    assert set(PAIRED_CODES.keys()) == expected_paired

    expected_protect = {
        "code_inline",
        "math_inline",
        "html_inline",
        "footnote_ref",
        "tasklist_item",
        "softbreak",
        "hardbreak",
    }
    assert set(PROTECT_CODES.keys()) == expected_protect

    expected_single = {"image"}
    assert set(SINGLE_TRANSLATE_CODES.keys()) == expected_single


def test_format_placeholder():
    """Тест форматирования плейсхолдеров."""
    assert format_placeholder("B_O", 1) == "__B_O_1__"
    assert format_placeholder("L_C", 42) == "__L_C_42__"
    assert format_placeholder("C", 7) == "__C_7__"


def test_get_code():
    """Тест получения кода для типов узлов."""
    # Парные теги
    assert get_code("strong_open", is_closing=False) == "B_O"
    assert get_code("strong_close", is_closing=True) == "B_C"
    assert get_code("em_open", is_closing=False) == "I_O"
    assert get_code("link_open", is_closing=False) == "L_O"

    # Одиночные теги
    assert get_code("code_inline") == "C"
    assert get_code("math_inline") == "M"
    assert get_code("image") == "G"
