from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pysbd
import regex as re

from .config import settings
from .languages import languages_db

# Проверить на разных значениях. Возможно, вынести в параметры
HARD_SENTENCE_TOKEN_LIMIT = 256

BLOCK_SPLIT_RE = re.compile(r"\n\s*\n+")


@dataclass(slots=True)
class TranslationChunk:
    text: str
    tokens: int
    sentences: int
    block_ix: int


@lru_cache(maxsize=32)
def get_segmenter(nllb_lang_code: str):
    lang = languages_db.get(nllb_lang_code)
    iso_lang_code = lang.get("iso2", "en") if lang else "en"
    segmenter = pysbd.Segmenter(language=iso_lang_code, clean=False)
    return segmenter


def split_blocks(text: str) -> list[str]:
    blocks = BLOCK_SPLIT_RE.split(text)
    return [block for block in blocks if block.strip()]


def split_sentences(text: str, nllb_lang_code: str) -> list[str]:
    # TODO: Возможно, побить абзац на предложения через FALLBACK_SENTENCE_RE - в каком случае может понадобиться?
    # FALLBACK_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
    segmenter = get_segmenter(nllb_lang_code)
    segments = segmenter.segment(text)

    # Если в начале блока был хоть один пробел - сохраняем один (чтоб не поломать разметку)
    result = [
        s if ix > 0 else (text[0] if text[0].isspace() else "") + s
        for ix, s in enumerate(segments)
    ]

    return result


def count_tokens(tokenizer, text: str) -> int:
    # TODO: Добавить типизацию encoder, fallback
    encoded = tokenizer(text, add_special_tokens=False, truncation=False)
    return len(encoded["input_ids"])


def split_long_sentence(tokenizer, sentence: str, max_tokens: int) -> list[str]:
    words = sentence.split()
    if not words:
        return []
    chunks: list[str] = []
    current_words: list[str] = [" "]
    for word in words:
        candidate_words = current_words + [word]
        candidate_text = " ".join(candidate_words)
        candidate_tokens = count_tokens(tokenizer, candidate_text)

        if current_words and candidate_tokens > max_tokens:
            chunks.append(" ".join(current_words))
            current_words = [" " + word]
        else:
            current_words.append(word)

    if current_words:
        chunks.append(" ".join(current_words))
    return chunks


def split_into_chunks(
    tokenizer,
    text: str,
    nllb_lang_code: str,
    max_tokens: int = settings.max_input_tokens,
) -> list[TranslationChunk]:
    blocks = split_blocks(text)
    chunks: list[TranslationChunk] = []
    current_sentences: list[str] = []
    current_tokens = 0
    current_sentence_count = 0
    current_block_ix = 0

    for block_ix, block in enumerate(blocks):
        sentences = split_sentences(block, nllb_lang_code)
        for sentence in sentences:
            sentence_tokens = count_tokens(tokenizer, sentence)

            # Обрабатываем большие предложения, если нужно
            sentence_parts = (
                split_long_sentence(tokenizer, sentence, max_tokens)
                if sentence_tokens > max_tokens
                else [sentence]
            )

            for part in sentence_parts:
                part_tokens = count_tokens(tokenizer, part)
                exceeds_limit = current_tokens + part_tokens > max_tokens
                block_changed = current_sentences and block_ix != current_block_ix

                if exceeds_limit or block_changed:
                    chunk_text = " ".join(current_sentences)
                    if chunk_text:
                        chunks.append(
                            TranslationChunk(
                                text=chunk_text,
                                tokens=current_tokens,
                                sentences=current_sentence_count,
                                block_ix=current_block_ix,
                            )
                        )
                    current_sentences = []
                    current_tokens = 0
                    current_sentence_count = 0

                current_sentences.append(part)
                current_tokens += part_tokens
                current_sentence_count += 1
                current_block_ix = block_ix

    # flush tail
    if current_sentences:
        chunk_text = " ".join(current_sentences)

        if chunk_text:
            chunks.append(
                TranslationChunk(
                    text=chunk_text,
                    tokens=current_tokens,
                    sentences=current_sentence_count,
                    block_ix=current_block_ix,
                )
            )
    return chunks
