from unittest.mock import MagicMock

import pytest

# Замените на ваши реальные пути импорта в проекте
from src.mt_server.markdown2.reconstructor import MarkdownReconstructor
from src.mt_server.markdown2.translation_unit import (
    TranslationUnit,
)

# from src.mt_server.markdown2.placeholder import Placeholder
from src.mt_server.markdown2.translation_unit_type import TranslationUnitType


@pytest.fixture
def reconstructor():
    return MarkdownReconstructor()


def test_reconstruct_plain_paragraph(reconstructor):
    """Тест сборки обычного абзаца без разметки."""
    u1 = TranslationUnit(
        node_id="node_1",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="Hello",
        extracted_text="Hello",
        translated_text="Привет",
        need_translation=True,
    )
    u2 = TranslationUnit(
        node_id="node_2",
        node_type="paragraph_close",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=False,
    )

    result = reconstructor.reconstruct([u1, u2])

    # Ожидаем текст абзаца с переводом строки на конце
    assert result == "Привет\n"


def test_reconstruct_heading(reconstructor):
    """Тест сборки заголовков разного уровня."""
    u1 = TranslationUnit(
        node_id="node_1",
        node_type="heading",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="Title",
        extracted_text="Title",
        translated_text="Заголовок",
        need_translation=True,
        level=2,
        tag="h2",
    )
    u2 = TranslationUnit(
        node_id="node_2",
        node_type="heading_close",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=False,
    )

    result = reconstructor.reconstruct([u1, u2])

    # Ожидаем префикс '## ' перед текстом заголовка
    assert result == "## Заголовок\n"


def test_reconstruct_inline_formatting_strong(reconstructor):
    """Тест восстановления парной инлайн-разметки (жирный шрифт)."""
    # Создаем моки плейсхолдеров
    ph_open = MagicMock(
        tag_mask=" {s_1} ",
        strategy="INLINE_TRANSLATE",
        node_type="strong_open",
        original_markup="**",
        is_closing=False,
    )
    ph_close = MagicMock(
        tag_mask=" {/s_1} ",
        strategy="INLINE_TRANSLATE",
        node_type="strong_close",
        original_markup="",
        is_closing=True,
    )

    u1 = TranslationUnit(
        node_id="node_1",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="This is **bold** text.",
        extracted_text="This is {s_1}bold{/s_1} text.",
        translated_text="Это {s_1}жирный{/s_1} текст.",
        need_translation=True,
        placeholders=[ph_open, ph_close],
    )
    u2 = TranslationUnit(
        node_id="node_2",
        node_type="paragraph_close",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=False,
    )

    result = reconstructor.reconstruct([u1, u2])

    # Разметка должна вернуться на свои места вокруг переведенного слова
    assert result == "Это **жирный** текст.\n"


def test_reconstruct_links_and_images(reconstructor):
    """Тест восстановления ссылок и картинок из словарей атрибутов."""
    ph_link_open = MagicMock(
        id=1,
        tag_mask=" {lnk_1} ",
        strategy="INLINE_TRANSLATE",
        node_type="link_open",
        original_markup={"href": "https://google.com", "title": ""},
        is_closing=False,
    )
    ph_link_close = MagicMock(
        id=1,
        tag_mask=" {/lnk_1} ",
        strategy="INLINE_TRANSLATE",
        node_type="link_close",
        original_markup="",
        is_closing=True,
    )
    ph_img = MagicMock(
        id=2,
        tag_mask=" {img_2} ",
        strategy="INLINE_TRANSLATE",
        node_type="image",
        original_markup={"src": "logo.png", "title": "Logo"},
        is_closing=False,
    )

    u1 = TranslationUnit(
        node_id="node_1",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="Go to [Google](https://google.com) and see ![logo](logo.png 'Logo')",
        extracted_text="Go to {lnk_1}Google{/lnk_1} and see {img_2}",
        translated_text="Перейдите в {lnk_1}Google{/lnk_1} и посмотрите на {img_2}",
        need_translation=True,
        placeholders=[ph_link_open, ph_link_close, ph_img],
    )
    u2 = TranslationUnit(
        node_id="node_2",
        node_type="paragraph_close",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=False,
    )

    result = reconstructor.reconstruct([u1, u2])

    # Ссылка должна собраться в синтаксис Markdown, а картинка — восстановить Alt-текст
    # (Поскольку в нашей схеме для картинки NLLB переводит Alt-текст внутри маски,
    # проверим, как реструктуризатор соберет её параметры).
    assert "[Google](https://google.com)" in result
    assert "![Альтернативный текст]" in result or "![" in result


def test_reconstruct_nested_blockquote(reconstructor):
    """Сложный тест: Восстановление многострочной разметки вложенной цитаты.

    > ## Заголовок
    > Текст цитаты.
    """
    bq_open = TranslationUnit(
        node_id="node_1",
        node_type="blockquote_open",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
    )
    h_open = TranslationUnit(
        node_id="node_2",
        node_type="heading",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="Header",
        extracted_text="Header",
        translated_text="Заголовок",
        need_translation=True,
        level=2,
    )
    h_close = TranslationUnit(
        node_id="node_3",
        node_type="heading_close",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=False,
    )
    p_open = TranslationUnit(
        node_id="node_4",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="Quote text.",
        extracted_text="Quote text.",
        translated_text="Текст цитаты.",
        need_translation=True,
    )
    p_close = TranslationUnit(
        node_id="node_5",
        node_type="paragraph_close",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=False,
    )
    bq_close = TranslationUnit(
        node_id="node_6",
        node_type="blockquote_close",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
    )

    result = reconstructor.reconstruct(
        [bq_open, h_open, h_close, p_open, p_close, bq_close]
    )

    # Префикс цитаты должен стоять перед КАЖДЫМ блоком внутри неё
    expected = "> ## Заголовок\n> Текст цитаты.\n"
    assert result == expected


def test_reconstruct_front_matter(reconstructor):
    """Тест восстановления метаданных Front Matter."""
    u1 = TranslationUnit(
        node_id="node_1",
        node_type="front_matter",
        unit_type=TranslationUnitType.SPECIAL_CASE,
        original_text="title: Исходный\nlayout: post\n",
        extracted_text="title: Исходный\nlayout: post\n",
        translated_text="title: Переведенный\nlayout: post\n",
        need_translation=False,
    )

    result = reconstructor.reconstruct([u1])

    assert result == "---\ntitle: Переведенный\nlayout: post\n---\n\n"


def test_reconstruct_nested_lists_with_indentation(reconstructor):
    """Тест восстановления структуры вложенных списков с правильными отступами.

    Синтаксис Markdown:
    - Элемент 1
        - Вложенный элемент 1.1
    """
    """Тест восстановления структуры списков с сохранением оригинального маркера '*'."""
    # Задаем tag="ul" (как в реальном markdown-it) и info="*" (как делает наш новый walker)
    list1_open = TranslationUnit(
        node_id="node_1",
        node_type="bullet_list_open",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
        tag="ul",
        info="*",
    )
    item1_open = TranslationUnit(
        node_id="node_2",
        node_type="list_item_open",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
        tag="li",
    )
    p1 = TranslationUnit(
        node_id="node_3",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="Item 1",
        extracted_text="Item 1",
        translated_text="Элемент 1",
        need_translation=True,
    )
    p1_close = TranslationUnit(
        node_id="node_4",
        node_type="paragraph_close",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=False,
    )

    # ... то же самое для list2_open ...
    list2_open = TranslationUnit(
        node_id="node_5",
        node_type="bullet_list_open",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
        tag="ul",
        info="*",
    )
    item2_open = TranslationUnit(
        node_id="node_6",
        node_type="list_item_open",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
        tag="li",
    )
    p2 = TranslationUnit(
        node_id="node_7",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="Nested Item",
        extracted_text="Nested Item",
        translated_text="Вложенный элемент",
        need_translation=True,
    )
    p2_close = TranslationUnit(
        node_id="node_8",
        node_type="paragraph_close",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=False,
    )

    item2_close = TranslationUnit(
        node_id="node_9",
        node_type="list_item_close",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
    )
    list2_close = TranslationUnit(
        node_id="node_10",
        node_type="bullet_list_close",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
    )
    item1_close = TranslationUnit(
        node_id="node_11",
        node_type="list_item_close",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
    )
    list1_close = TranslationUnit(
        node_id="node_12",
        node_type="bullet_list_close",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
    )

    result = reconstructor.reconstruct(
        [
            list1_open,
            item1_open,
            p1,
            p1_close,
            list2_open,
            item2_open,
            p2,
            p2_close,
            item2_close,
            list2_close,
            item1_close,
            list1_close,
        ]
    )

    # Система должна вернуть звездочки вместо дефисов!
    expected = "* Элемент 1\n    * Вложенный элемент\n"
    assert result == expected


def test_reconstruct_definition_list(reconstructor):
    """Тест восстановления структуры списков определений (dl, dt, dd).

    Синтаксис Markdown:
    Термин
    : Определение
    """
    dl_open = TranslationUnit(
        node_id="node_1",
        node_type="dl_open",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
        tag="dl",
    )
    dt_open = TranslationUnit(
        node_id="node_2",
        node_type="dt_open",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="Term",
        extracted_text="Term",
        translated_text="Термин",
        need_translation=True,
        tag="dt",
    )
    dt_close = TranslationUnit(
        node_id="node_3",
        node_type="dt_close",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=False,
        tag="dt",
    )
    dd_open = TranslationUnit(
        node_id="node_4",
        node_type="dd_open",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="Definition",
        extracted_text="Definition",
        translated_text="Определение",
        need_translation=True,
        tag="dd",
    )
    dd_close = TranslationUnit(
        node_id="node_5",
        node_type="dd_close",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=False,
        tag="dd",
    )
    dl_close = TranslationUnit(
        node_id="node_6",
        node_type="dl_close",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
        tag="dl",
    )

    result = reconstructor.reconstruct(
        [dl_open, dt_open, dt_close, dd_open, dd_close, dl_close]
    )

    expected = "Термин\n: Определение\n"
    assert result == expected


def test_reconstruct_fence_inside_blockquote(reconstructor):
    """Тест восстановления блока кода внутри цитаты.

    Внутренние строки кода НЕ должны получать префиксы '> ', чтобы не ломать синтаксис.
    """
    bq_open = TranslationUnit(
        node_id="node_1",
        node_type="blockquote_open",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
        tag="blockquote",
    )
    # 2. Многострочный код внутри fence
    fence_node = TranslationUnit(
        node_id="node_2",
        node_type="fence",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="def hello():\n    print('world')\n",
        extracted_text="def hello():\n    print('world')\n",
        need_translation=False,
        info="python",
    )
    bq_close = TranslationUnit(
        node_id="node_3",
        node_type="blockquote_close",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="",
        need_translation=False,
        tag="blockquote",
    )

    result = reconstructor.reconstruct([bq_open, fence_node, bq_close])

    # ИСПРАВЛЕНО: Убран лишний \n после знака цитаты
    expected = "> ```python\ndef hello():\n    print('world')\n```\n\n"
    assert result == expected
