from dataclasses import dataclass, field
from typing import List

import regex as re

from mt_server.utils import count_tokens, split_sentences

from .translation_unit import TranslationUnit


@dataclass(slots=True)
class ChunkSegment:
    """Атомарная единица текста (предложение или его часть) внутри чанка."""

    unit_id: str  # Идентификатор родительского TranslationUnit (node_id)
    text: str  # Текст сегмента с масками разметки (например, "Это {s_1}важно{/s_1}")


@dataclass(slots=True)
class MarkdownChunk:
    """Пакет данных (чанк), подготовленный для передачи в TranslationEngine NLLB."""

    chunk_id: int
    segments: List[ChunkSegment] = field(default_factory=list)

    # Метрики для жесткого контроля лимитов токенизатора
    token_count: int = 0
    sentence_count: int = 0

    def to_plain_text(self) -> str:
        """Собирает все сегменты чанка в единую строку для отправки в модель.

        Использует видимый текстовый маркер ' ||| ' в качестве разделителя границ.
        Модель NLLB гарантированно переносит его без изменений, что позволит
        выполнить точный обратный сплит.
        """
        if not self.segments:
            return ""

        # Склеиваем все извлеченные сегменты через наш безопасный маркер
        return " ||| ".join(seg.text for seg in self.segments)


class MarkdownChunker:
    """Отвечает за упаковку TranslationUnit в лимитированные чанки NLLB и обратный мерж перевода."""

    # Регулярное выражение для безопасного токенизации строки.
    # Находит: маски в фигурных скобках ({...}), последовательности пробелов (\s+),
    # или любые другие символы, не являющиеся пробелами (\S+).
    # Использование групп гарантирует, что мы не потеряем пробелы при разборе.
    _SAFE_SPLIT_RE = re.compile(r"(\{[^}]+\})|(\s+)|(\S+)")

    def __init__(self, tokenizer, max_tokens: int, nllb_lang_code: str):
        self.tokenizer = tokenizer
        self.max_tokens = max_tokens
        self.lang_code = nllb_lang_code
        self.chunks: List["MarkdownChunk"] = []

    def create_chunks(self, units: List[TranslationUnit]) -> List["MarkdownChunk"]:
        """Основной метод упаковки юнитов в чанки.

        Принимает плоский список от ASTWalker, фильтрует по need_translation,
        разбивает тексты юнитов на предложения через pysbd и жадно формирует чанки.
        """
        self.chunks = []
        chunk_counter = 1
        current_chunk = MarkdownChunk(chunk_id=chunk_counter)

        # 1. Отбираем только те юниты, которые действительно требуют перевода (CONTEXT_BLOCK)
        translatable_units = [u for u in units if u.need_translation]

        for unit in translatable_units:
            # 2. Сегментируем текст юнита на отдельные предложения
            sentences = split_sentences(unit.extracted_text, self.lang_code)

            for sentence in sentences:
                if not sentence.strip():
                    continue

                # Считаем токены для текущего предложения
                sentence_tokens = count_tokens(self.tokenizer, sentence)

                # Пограничный случай: если ОДНО предложение само по себе превышает лимит чанка,
                # мы безопасно нарезаем его на под-части, не разрывая маски плейсхолдеров
                sentence_parts = (
                    self._safe_split_long_sentence(sentence)
                    if sentence_tokens > self.max_tokens
                    else [sentence]
                )

                for part in sentence_parts:
                    # Экранируем маркеры '|||', если пользователь написал их внутри предложения
                    escaped_part = self._escape_marker(part)
                    part_tokens = count_tokens(self.tokenizer, escaped_part)

                    # 3. Проверяем, помещается ли текущий сегмент в текущий чанк
                    if current_chunk.segments and (
                        current_chunk.token_count + part_tokens > self.max_tokens
                    ):
                        # Чанк заполнен, сохраняем его в список и открываем новый
                        self.chunks.append(current_chunk)
                        chunk_counter += 1
                        current_chunk = MarkdownChunk(chunk_id=chunk_counter)

                    # 4. Записываем сегмент в чанк и обновляем метрики
                    current_chunk.segments.append(
                        ChunkSegment(unit_id=unit.node_id, text=escaped_part)
                    )
                    current_chunk.token_count += part_tokens
                    current_chunk.sentence_count += 1

        # Фиксируем остаток (последний открытый чанк)
        if current_chunk.segments:
            self.chunks.append(current_chunk)

        return self.chunks

    def merge_translations(
        self,
        chunks: List["MarkdownChunk"],
        translated_texts: List[str],
        units: List[TranslationUnit],
    ):
        """Метод обратной сборки (Merger).

        Принимает список чанков, плоский список строк ответов от NLLB Engine (один ответ на один чанк),
        нарезает ответы по маркеру '|||' и раскладывает по соответствующим TranslationUnit
        в поле translated_text.
        """
        # Превращаем units в словарь для быстрого O(1) доступа по node_id
        unit_map = {u.node_id: u for u in units}

        # Инициализируем переводы и сразу маркируем пустые юниты
        # Сначала очищаем поле translated_text у всех переводимых юнитов,
        # так как мы будем дописывать туда куски инкрементально
        for u in units:
            if u.need_translation:
                u.translated_text = ""
                if not u.extracted_text.strip():
                    # Пустой узел считается успешно "переведенным"
                    u.is_translated = True

        for chunk, response_text in zip(chunks, translated_texts):
            if not response_text.strip():
                continue

            translated_segments = [s.strip() for s in response_text.split("|||")]

            if len(translated_segments) == len(chunk.segments):
                for seg, translated_text in zip(chunk.segments, translated_segments):
                    unit = unit_map[seg.unit_id]
                    unescaped_text = self._unescape_marker(translated_text)

                    if unit.translated_text:
                        unit.translated_text += " " + unescaped_text
                    else:
                        unit.translated_text = unescaped_text
                    unit.is_translated = True
            else:
                self._fallback_align_segments(chunk, translated_segments, unit_map)

    def _fallback_align_segments(
        self, chunk: "MarkdownChunk", translated_segments: List[str], unit_map: dict
    ):
        """Аварийный гибридный алгоритм спасения данных при нарушении разметки маркеров."""
        # Регулярка для быстрого поиска масок плейсхолдеров в переведенной строке
        mask_pattern = re.compile(r"\{[^}]+\}")

        # Копия списка исходных сегментов текущего чанка для скользящего отслеживания хронологии
        remaining_segments = list(chunk.segments)
        unaligned_translations = []

        # --- ЭТАП А: Выравнивание по якорям (Маскам разметки) ---
        for trans_text in translated_segments:
            # Ищем маски в текущей переведенной строке
            found_masks = mask_pattern.findall(trans_text)

            success_matched = False
            if found_masks:
                # Берем первую найденную маску и ищем её в реестре оригинальных сегментов чанка
                for mask in found_masks:
                    # Ищем, какому исходному сегменту принадлежала эта маска
                    matched_seg = next(
                        (s for s in remaining_segments if mask in s.text), None
                    )
                    if matched_seg:
                        unit = unit_map[matched_seg.unit_id]
                        unescaped_text = self._unescape_marker(trans_text)

                        if unit.translated_text:
                            unit.translated_text += " " + unescaped_text
                        else:
                            unit.translated_text = unescaped_text
                        unit.is_translated = True

                        # Удаляем спасенный сегмент из списка ожидания, чтобы не задублировать
                        remaining_segments.remove(matched_seg)
                        success_matched = True
                        break

            # Если масок в строке не было или мы не нашли совпадения - откладываем строку на Этап Б
            if not success_matched:
                unaligned_translations.append(trans_text)

        # --- ЭТАП Б: Хронологическая привязка остатков (Для обычного текста без разметки) ---
        # Распределяем оставшиеся "слепые" переводы по оставшимся исходным сегментам один к одному
        for trans_text in unaligned_translations:
            if not remaining_segments:
                # Модель сгенерировала фантомный избыточный текст, привязываем его к самому последнему у юниту чанка
                last_unit = unit_map[chunk.segments[-1].unit_id]
                last_unit.translated_text += " " + self._unescape_marker(trans_text)
                continue

            # Берем первый хронологически идущий пустой сегмент
            current_seg = remaining_segments.pop(0)
            unit = unit_map[current_seg.unit_id]
            unescaped_text = self._unescape_marker(trans_text)

            if unit.translated_text:
                unit.translated_text += " " + unescaped_text
            else:
                unit.translated_text = unescaped_text
            unit.is_translated = True

        # Если после всего этого в чанке остались исходные сегменты, которые так и не получили перевод
        # (модель их "съела"), помечаем родительские юниты ошибкой для последующего точечного перезапроса
        for dead_seg in remaining_segments:
            unit = unit_map[dead_seg.unit_id]
            if not unit.translated_text:
                unit.has_errors = True
                unit.error_message = "Translation segment dropped by NLLB engine during chunk formatting anomaly."

    def _escape_marker(self, text: str) -> str:
        """Экранирует пользовательские символы '|||', чтобы они не сломали сплиттер чанка."""
        return text.replace("|||", "__TRIPLE_PIPE__")

    def _unescape_marker(self, text: str) -> str:
        """Возвращает оригинальные символы '|||' в переведенный текст."""
        return text.replace("__TRIPLE_PIPE__", "|||")

    def _safe_split_long_sentence(self, sentence: str) -> List[str]:
        """Безопасно нарезает аномально длинное предложение на под-части по пробелам.

        Гарантирует, что маски плейсхолдеров типа {s_1} останутся целыми.
        """
        matches = self._SAFE_SPLIT_RE.findall(sentence)

        # ИСПРАВЛЕНО ВАМИ: Элегантное и надежное развертывание групп в плоский список
        tokens_pool = [g for groups in matches for g in groups if g]

        if not tokens_pool:
            return []

        sub_chunks: List[str] = []
        current_words: List[str] = []
        current_tokens = 0

        for item in tokens_pool:
            item_tokens = count_tokens(self.tokenizer, item)

            # ЗАЩИТНЫЙ EDGE-CASE: Если ОДИН токен сам по себе больше лимита
            if item_tokens > self.max_tokens:
                # Если в буфере уже что-то скопилось - сбрасываем это в отдельный чанк
                if current_words:
                    sub_chunks.append("".join(current_words).strip())
                    current_words = []
                    current_tokens = 0

                # Отдаем этот сверхдлинный элемент целиком как изолированный чанк
                sub_chunks.append(item.strip())
                continue

            # Стандартная жадная упаковка
            if current_words and (current_tokens + item_tokens > self.max_tokens):
                sub_chunks.append("".join(current_words).strip())
                current_words = [item]
                current_tokens = item_tokens
            else:
                current_words.append(item)
                current_tokens += item_tokens

        # Сбрасываем хвост
        if current_words:
            sub_chunks.append("".join(current_words).strip())

        return [sc for sc in sub_chunks if sc]
