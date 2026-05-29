import logging
from dataclasses import dataclass, field
from typing import List

import regex as re

from mt_server.utils import count_tokens, split_sentences

from .translation_unit import TranslationUnit

logger = logging.getLogger("uvicorn.error")


@dataclass(slots=True)
class ChunkSegment:
    """Атомарная единица текста (предложение или его часть) внутри чанка."""

    unit_id: str
    text: str


@dataclass(slots=True)
class MarkdownChunk:
    """Пакет данных (чанк), подготовленный для передачи в TranslationEngine NLLB."""

    chunk_id: int
    segments: List[ChunkSegment] = field(default_factory=list)
    token_count: int = 0
    sentence_count: int = 0

    def to_plain_text(self) -> str:
        """Собирает все сегменты чанка в единую строку для отправки в модель.

        Использует непечатный ASCII символ \\x1E (Record Separator).
        NLLB гарантированно переносит его без изменений.
        """
        if not self.segments:
            return ""
        return "\x1e".join(seg.text for seg in self.segments)


class MarkdownChunker:
    """Управляет упаковкой TranslationUnit в лимитированные чанки NLLB и обратным мержем."""

    _SAFE_SPLIT_RE = re.compile(r"(\{[^}]+\})|(\s+)|(\S+)")

    def __init__(self, tokenizer, max_tokens: int, nllb_lang_code: str):
        self.tokenizer = tokenizer
        self.max_tokens = max_tokens
        self.lang_code = nllb_lang_code
        self.chunks: List[MarkdownChunk] = []

    def _count_tokens(self, text: str) -> int:
        return count_tokens(self.tokenizer, text)

    def create_chunks(self, units: List[TranslationUnit]) -> List[MarkdownChunk]:
        """Основной метод упаковки юнитов в чанки."""
        self.chunks = []
        chunk_counter = 1
        current_chunk = MarkdownChunk(chunk_id=chunk_counter)

        translatable_units = [u for u in units if u.need_translation]

        logger.debug(
            "Creating chunks from %d translatable units", len(translatable_units)
        )

        for unit in translatable_units:
            sentences = split_sentences(unit.extracted_text, self.lang_code)

            for sentence in sentences:
                if not sentence.strip():
                    continue

                sentence_tokens = self._count_tokens(sentence)

                sentence_parts = (
                    self._safe_split_long_sentence(sentence)
                    if sentence_tokens > self.max_tokens
                    else [sentence]
                )

                for part in sentence_parts:
                    part_tokens = self._count_tokens(part)

                    if current_chunk.segments and (
                        current_chunk.token_count + part_tokens > self.max_tokens
                    ):
                        logger.debug(
                            "  Chunk %d full (%d tokens), creating new chunk",
                            chunk_counter,
                            current_chunk.token_count,
                        )
                        self.chunks.append(current_chunk)
                        chunk_counter += 1
                        current_chunk = MarkdownChunk(chunk_id=chunk_counter)

                    # Пишем чистый текст напрямую, экранирование ||| больше не требуется!
                    current_chunk.segments.append(
                        ChunkSegment(unit_id=unit.node_id, text=part)
                    )
                    current_chunk.token_count += part_tokens
                    current_chunk.sentence_count += 1

        if current_chunk.segments:
            self.chunks.append(current_chunk)

        logger.info("Chunks created: total=%d chunks", len(self.chunks))

        return self.chunks

    def _safe_split_long_sentence(self, sentence: str) -> List[str]:
        """Безопасно нарезает аномально длинное предложение на под-части по пробелам."""
        matches = self._SAFE_SPLIT_RE.findall(sentence)
        tokens_pool = [g for groups in matches for g in groups if g]

        if not tokens_pool:
            return []

        sub_chunks: List[str] = []
        current_words: List[str] = []
        current_tokens = 0

        for item in tokens_pool:
            item_tokens = self._count_tokens(item)

            if item_tokens > self.max_tokens:
                if current_words:
                    sub_chunks.append("".join(current_words).strip())
                    current_words = []
                    current_tokens = 0
                sub_chunks.append(item.strip())
                continue

            if current_words and (current_tokens + item_tokens > self.max_tokens):
                sub_chunks.append("".join(current_words).strip())
                current_words = [item]
                current_tokens = item_tokens
            else:
                current_words.append(item)
                current_tokens += item_tokens

        if current_words:
            sub_chunks.append("".join(current_words).strip())

        return [sc for sc in sub_chunks if sc]

    def merge_translations(
        self,
        chunks: List[MarkdownChunk],
        translated_texts: List[str],
        units: List[TranslationUnit],
    ):
        """Метод обратной сборки (Merger). Точно нарезает ответы по символу \\x1E."""
        unit_map = {u.node_id: u for u in units}

        for u in units:
            if u.need_translation:
                u.translated_text = ""
                if not u.extracted_text.strip():
                    u.is_translated = True

        logger.debug("Merging translations for %d chunks", len(chunks))

        for i, (chunk, response_text) in enumerate(zip(chunks, translated_texts)):
            if not response_text.strip():
                logger.warning("  Chunk %d: empty translation response", i + 1)
                continue

            # Нарезаем строго по непечатному ASCII управляющему разделителю \x1E
            translated_segments = [s.strip() for s in response_text.split("\x1e")]

            if len(translated_segments) == len(chunk.segments):
                for seg, translated_text in zip(chunk.segments, translated_segments):
                    unit = unit_map[seg.unit_id]

                    if unit.translated_text:
                        unit.translated_text += " " + translated_text
                    else:
                        unit.translated_text = translated_text
                    unit.is_translated = True

                logger.debug(
                    "Chunk %d: successfully merged %d segments",
                    i + 1,
                    len(translated_segments),
                )
            else:
                logger.warning(
                    "Chunk %d: segment mismatch (expected=%d, got=%d), using fallback",
                    i + 1,
                    len(chunk.segments),
                    len(translated_segments),
                )
                # В случае редкой аномалии (если модель вырезала байт-токен), спасаем данные гибридным алгоритмом
                self._fallback_align_segments(chunk, translated_segments, unit_map)
        merged_count = sum(1 for u in units if u.is_translated and u.need_translation)
        logger.info("Merge complete: %d units translated", merged_count)

    def _fallback_align_segments(
        self, chunk: MarkdownChunk, translated_segments: List[str], unit_map: dict
    ):
        """Аварийный гибридный алгоритм спасения данных по маскам-якорям."""
        mask_pattern = re.compile(r"\{[^}]+\}")
        remaining_segments = list(chunk.segments)
        unaligned_translations = []

        for trans_text in translated_segments:
            found_masks = mask_pattern.findall(trans_text)
            success_matched = False

            if found_masks:
                for mask in found_masks:
                    matched_seg = next(
                        (s for s in remaining_segments if mask in s.text), None
                    )
                    if matched_seg:
                        unit = unit_map[matched_seg.unit_id]
                        if unit.translated_text:
                            unit.translated_text += " " + trans_text
                        else:
                            unit.translated_text = trans_text
                        unit.is_translated = True
                        remaining_segments.remove(matched_seg)
                        success_matched = True
                        break

            if not success_matched:
                unaligned_translations.append(trans_text)

        for trans_text in unaligned_translations:
            if not remaining_segments:
                last_unit = unit_map[chunk.segments[-1].unit_id]
                last_unit.translated_text += " " + trans_text
                continue

            current_seg = remaining_segments.pop(0)
            unit = unit_map[current_seg.unit_id]
            if unit.translated_text:
                unit.translated_text += " " + trans_text
            else:
                unit.translated_text = trans_text
            unit.is_translated = True

        for dead_seg in remaining_segments:
            unit = unit_map[dead_seg.unit_id]
            if not unit.translated_text:
                unit.has_errors = True
                unit.error_message = "Segment dropped by NLLB anomaly."
