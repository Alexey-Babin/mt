from unittest.mock import MagicMock

import pytest
from src.mt_server.markdown2.placeholder import PlaceholderManager


# Фикстура для создания свежего менеджера перед каждым тестом
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
    assert ph.tag_mask == " { code_1 } "
    assert ph.strategy == "INLINE_PROTECT"
    assert ph.original_markup == "`pip install pytest`"
    assert ph.is_closing is False
    assert "{ code_1 }" in manager.registry


def test_create_placeholder_inline_protect_math(manager):
    """Тест изоляции формул через MagicMock."""
    node = MagicMock()
    node.type = "math_inline"
    node.content = "E=mc^2"

    ph = manager.create_placeholder(node)

    assert ph.tag_mask == " { math_1 } "
    assert ph.original_markup == "$E=mc^2$"


def test_create_placeholder_paired_tags_stack_logic(manager):
    """Тест проверки вложенности и синхронизации ID через стек (MagicMock)."""
    strong_open = MagicMock(type="strong_open", markup="**")
    em_open = MagicMock(type="em_open", markup="_")
    em_close = MagicMock(type="em_close", markup="_")
    strong_close = MagicMock(type="strong_close", markup="**")

    # 1. Открываем strong
    ph_s_open = manager.create_placeholder(strong_open)
    assert ph_s_open.tag_mask == " { s_1 } "
    assert ph_s_open.original_markup == "**"

    # 2. Открываем em
    ph_e_open = manager.create_placeholder(em_open)
    assert ph_e_open.tag_mask == " { e_2 } "
    assert ph_e_open.original_markup == "_"

    # 3. Закрываем em
    ph_e_close = manager.create_placeholder(em_close)
    assert ph_e_close.tag_mask == " { /e_2 } "
    assert ph_e_close.original_markup == ""

    # 4. Закрываем strong
    ph_s_close = manager.create_placeholder(strong_close)
    assert ph_s_close.tag_mask == " { /s_1 } "
    assert ph_s_close.original_markup == ""


def test_create_placeholder_link_attributes(manager):
    """Тест извлечения атрибутов ссылки через MagicMock."""
    node_open = MagicMock(type="link_open")
    node_open.attrs = {"href": "https://google.com", "title": "Google"}

    node_close = MagicMock(type="link_close")
    node_close.attrs = None  # Имитируем отсутствие атрибутов у закрывающего тега

    ph_open = manager.create_placeholder(node_open)
    ph_close = manager.create_placeholder(node_close)

    assert ph_open.tag_mask == " { lnk_1 } "
    assert isinstance(ph_open.original_markup, dict)
    assert ph_open.original_markup["href"] == "https://google.com"
    assert ph_open.original_markup["title"] == "Google"

    assert ph_close.tag_mask == " { /lnk_1 } "
    assert ph_close.original_markup == ""


def test_create_placeholder_image_as_inline_translate(manager):
    """Тест обработки картинок через MagicMock."""
    node = MagicMock(type="image")
    node.content = "Альтернативный текст"
    node.attrs = {"src": "logo.png"}

    ph = manager.create_placeholder(node)

    assert ph.tag_mask == " { img_1 } "
    assert ph.strategy == "INLINE_TRANSLATE"
    assert ph.is_closing is False
    assert ph.original_markup["src"] == "logo.png"


def test_edge_case_unbalanced_closing_tag(manager):
    """Edge case: Внезапный закрывающий тег без открывающего (MagicMock)."""
    node_close = MagicMock(type="strong_close")
    node_close.attrs = None

    ph = manager.create_placeholder(node_close)

    assert ph.tag_mask == " { /s_1 } "
    assert ph.is_closing is True
    assert ph.original_markup == ""


def test_edge_case_unknown_node_type_fallback(manager):
    """Edge case: Неизвестный тип токена (MagicMock)."""
    node = MagicMock(type="some_rare_future_plugin_token")
    node.content = "raw text"
    node.attrs = None

    ph = manager.create_placeholder(node)

    assert ph.tag_mask == " { ph_1 } "
    assert ph.strategy == "INLINE_PROTECT"
    assert ph.original_markup == "raw text"
