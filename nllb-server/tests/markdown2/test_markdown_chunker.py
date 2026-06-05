import pytest

# Замените на ваши реальные пути импорта внутри проекта
from src.mt_server.markdown2.chunker import (
    ChunkSegment,
    MarkdownChunk,
    MarkdownChunker,
)
from src.mt_server.markdown2.models.placeholder_codes import SEGMENT_SEPARATOR
from src.mt_server.markdown2.models.translation_unit import TranslationUnit
from src.mt_server.markdown2.models.translation_unit_type import TranslationUnitType

# --- Вспомогательные фикстуры и моки ---


class MockTokenizer:
    """Имитатор токенизатора.

    Считает токеном каждое слово. Если слово является длинной маской плейсхолдера,
    оно весит пропорционально своей длине, имитируя BPE-токенизацию NLLB.
    """

    def __call__(self, text: str, **kwargs):
        words = [w for w in text.split() if w]
        total_tokens = 0
        for w in words:
            if w.startswith("{") and len(w) > 10:
                # Длинный плейсхолдер весит много токенов
                total_tokens += 5
            else:
                total_tokens += 1
        return {"input_ids": [0] * total_tokens}


@pytest.fixture
def tokenizer():
    return MockTokenizer()


@pytest.fixture
def chunker(tokenizer):
    # Создаем чанкер с небольшим лимитом токенов (например, 10), чтобы легко триггерить переносы
    return MarkdownChunker(
        tokenizer=tokenizer, max_tokens=10, nllb_lang_code="rus_Cyrl"
    )


# --- Тесты упаковки (create_chunks) ---


def test_create_chunks_basic_greedy_packing(chunker):
    """Тест базовой жадной упаковки нескольких маленьких TranslationUnit."""
    u1 = TranslationUnit(
        node_id="node_1",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="Первое короткое предложение.",
        need_translation=True,
    )
    u2 = TranslationUnit(
        node_id="node_2",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="Второе предложение документа.",
        need_translation=True,
    )
    u3 = TranslationUnit(
        node_id="node_3",
        node_type="heading",
        unit_type=TranslationUnitType.STRUCTURAL_IGNORE,
        original_text="",
        extracted_text="Игнорируемый каркас",
        need_translation=False,  # НЕ должен попасть в чанк
    )

    chunks = chunker.create_chunks([u1, u2, u3])

    # Оба переводимых предложения суммарно весят 3 + 3 = 6 токенов (меньше лимита 10)
    # Они должны упаковаться в один чанк
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_id == 1
    assert len(chunk.segments) == 2
    assert chunk.segments[0].unit_id == "node_1"
    assert chunk.segments[1].unit_id == "node_2"

    # Проверяем склейку через маркер
    assert (
        chunk.to_plain_text()
        == f"Первое короткое предложение.{SEGMENT_SEPARATOR}Второе предложение документа."
    )


def test_create_chunks_trigger_max_tokens_split(chunker):
    """Тест переноса сегментов в новый чанк при превышении max_tokens."""
    # Уменьшаем лимит до 4 токенов для этого теста
    chunker.max_tokens = 4

    u1 = TranslationUnit(
        node_id="node_1",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="Раз два три.",
        need_translation=True,  # 3 токена
    )
    u2 = TranslationUnit(
        node_id="node_2",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="Четыре пять шесть.",
        need_translation=True,  # 3 токена
    )

    chunks = chunker.create_chunks([u1, u2])

    # Суммарно 6 токенов, лимит чанка 4. Должно сформироваться 2 чанка.
    assert len(chunks) == 2
    assert chunks[0].segments[0].unit_id == "node_1"
    assert chunks[1].segments[0].unit_id == "node_2"


def test_safe_split_long_sentence_protects_masks(chunker):
    """Тест нарезки сверхдлинного предложения: маски {...} не должны разрываться."""
    chunker.max_tokens = 3
    # Каждое слово/маска 1 токен. Маска {lnk_1} должна остаться целой.
    sentence = "Начало длинного текста {lnk_1}продолжение{/lnk_1} конец."

    parts = chunker._safe_split_long_sentence(sentence)

    # Регулярное выражение должно было разбить текст, сохранив маски
    # Проверяем, что ни в одной из подстрок маска не оказалась разрезанной пополам
    for part in parts:
        if "{" in part:
            assert (
                "}" in part
            )  # Если открылась скобка, она обязана закрыться в этой же части


def test_safe_split_long_sentence_indivisible_token_protection(chunker):
    """Тест защиты от зависания, если ОДИН токен больше лимита max_tokens."""
    chunker.max_tokens = 2
    # Сверхдлинный неделимый элемент (например, монолитный плейсхолдер кода)
    sentence = "Короткое {code_99999999999999999999}"

    parts = chunker._safe_split_long_sentence(sentence)

    # Система не должна уйти в бесконечный цикл. Она должна выплюнуть 2 части
    assert len(parts) == 2
    assert parts[0] == "Короткое"
    assert parts[1] == "{code_99999999999999999999}"


# --- Тесты обратного разбора (merge_translations) ---


def test_merge_translations_ideal_scenario(chunker):
    """Тест мержа в идеальном сценарии: количество маркеров \x1e совпало на 100%."""
    u1 = TranslationUnit(
        node_id="node_1",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=True,
    )
    u2 = TranslationUnit(
        node_id="node_2",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=True,
    )

    chunk = MarkdownChunk(chunk_id=1)
    chunk.segments = [
        ChunkSegment(
            unit_id="node_1",
            text="Текст один с |||",  # Пользовательский пайп идет внутри текста как есть
        ),
        ChunkSegment(unit_id="node_2", text="Текст два"),
    ]

    # Передаем строку ответа модели, разделенную SEGMENT_SEPARATOR
    translated_response = (
        f"Translated text one with |||{SEGMENT_SEPARATOR}Translated text two"
    )

    chunker.merge_translations([chunk], [translated_response], [u1, u2])

    # Проверяем, что перевод разложился по юнитам без ложных срабатываний fallback
    assert u1.translated_text == "Translated text one with |||"
    assert u1.is_translated is True
    assert u2.translated_text == "Translated text two"
    assert u2.is_translated is True


def test_merge_translations_fallback_by_masks(chunker):
    """Тест аварийного мержа: модель стерла маркер \\x1e, но у нас есть маски-якоря."""
    u1 = TranslationUnit(
        node_id="node_1",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=True,
    )
    u2 = TranslationUnit(
        node_id="node_2",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=True,
    )

    chunk = MarkdownChunk(chunk_id=1)
    chunk.segments = [
        ChunkSegment(unit_id="node_1", text="Текст {s_1}важно{/s_1}"),
        ChunkSegment(unit_id="node_2", text="Обычный текст без разметки"),
    ]

    # Аномальный ответ от NLLB: модель склеила строки, маркер ||| пропал!
    # "Translated {s_1}important{/s_1} and regular text without markup"
    translated_response = (
        "Translated {s_1}important{/s_1} and regular text without markup"
    )

    chunker.merge_translations([chunk], [translated_response], [u1, u2])

    # Благодаря Этапу А (якоря разметки), предложение с маской {s_1}
    # должно безошибочно привязаться к первому юниту, несмотря на отсутствие |||
    assert (
        u1.translated_text
        == "Translated {s_1}important{/s_1} and regular text without markup"
    )
    assert u1.is_translated is True


def test_merge_translations_fallback_chronological_drop_error(chunker):
    """Тест аварийного мержа: модель полностью "съела" перевод второго сегмента."""
    u1 = TranslationUnit(
        node_id="node_1",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=True,
    )
    u2 = TranslationUnit(
        node_id="node_2",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=True,
    )

    chunk = MarkdownChunk(chunk_id=1)
    chunk.segments = [
        ChunkSegment(unit_id="node_1", text="Предложение один"),
        ChunkSegment(unit_id="node_2", text="Предложение два"),
    ]

    # Модель вернула только перевод первого сегмента, второй исчез
    translated_response = "Only translated first segment"

    chunker.merge_translations([chunk], [translated_response], [u1, u2])

    # Первый юнит получит перевод (по хронологии Этапа Б)
    assert u1.translated_text == "Only translated first segment"

    # Второй юнит останется пустым и получит флаг ошибки для последующего перезапроса
    assert u2.translated_text == ""
    assert u2.has_errors is True
    assert u2.error_message and "dropped by NLLB" in u2.error_message


def test_merge_translations_keeps_empty_segments_preventing_false_fallback(chunker):
    """Тест сохранения пустых сегментов.

    Если модель вернула два разделителя подряд (пустой сегмент между ними),
    система НЕ должна отфильтровать его. Длины должны совпасть, исключая ложный fallback.
    """
    u1 = TranslationUnit(
        node_id="node_1",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="Фраза один",
        need_translation=True,
    )
    u2 = TranslationUnit(
        node_id="node_2",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="Фраза два",
        need_translation=True,
    )
    u3 = TranslationUnit(
        node_id="node_3",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="Фраза три",
        need_translation=True,
    )

    chunk = MarkdownChunk(chunk_id=1)
    chunk.segments = [
        ChunkSegment(unit_id="node_1", text="Фраза один"),
        ChunkSegment(unit_id="node_2", text="Фраза два"),
        ChunkSegment(unit_id="node_3", text="Фраза три"),
    ]

    # Имитируем ответ модели, где второй сегмент перевелся как пустая строка (два разделителя подряд)
    translated_response = (
        f"Translated one{SEGMENT_SEPARATOR} {SEGMENT_SEPARATOR}Translated three"
    )

    # Запускаем мерж. Если пустая строка отфильтруется, длина станет 2 вместо 3, и включится fallback.
    # Мы проверяем, что отработал идеальный линейный сценарий.
    chunker.merge_translations([chunk], [translated_response], [u1, u2, u3])

    assert u1.translated_text == "Translated one"
    assert u1.is_translated is True

    # Второй узел честно получил пустую строку и пометился как переведенный, без ошибок fallback
    assert u2.translated_text == ""
    assert u2.is_translated is True
    assert u2.has_errors is False

    assert u3.translated_text == "Translated three"
    assert u3.is_translated is True


def test_merge_translations_handles_empty_units_without_segments(chunker):
    """Тест обработки юнитов, у которых изначально пустойextracted_text (например, пустая ячейка таблицы).

    Они не создают сегментов в чанках, но должны получить статус is_translated=True.
    """
    # Нормальный юнит с текстом (порождает сегмент)
    u1 = TranslationUnit(
        node_id="node_1",
        node_type="paragraph",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="Есть текст",
        need_translation=True,
    )
    # Аномальный пустой юнит (например, пустая ячейка таблицы или пустой параграф)
    u2 = TranslationUnit(
        node_id="node_2",
        node_type="td",
        unit_type=TranslationUnitType.CONTEXT_BLOCK,
        original_text="",
        extracted_text="",
        need_translation=True,  # need_translation=True, но текста нет
    )

    # В чанк попадет только сегмент от u1
    chunk = MarkdownChunk(chunk_id=1)
    chunk.segments = [ChunkSegment(unit_id="node_1", text="Есть текст")]

    translated_response = "Translated text"

    chunker.merge_translations([chunk], [translated_response], [u1, u2])

    # u1 получает свой перевод
    assert u1.translated_text == "Translated text"
    assert u1.is_translated is True

    # u2 не имеет перевода (остался пустым), но обязан получить флаг успешного прохождения конвейера
    assert u2.translated_text == ""
    assert u2.is_translated is True
    assert u2.has_errors is False
