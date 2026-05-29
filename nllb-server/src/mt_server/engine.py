import os
import re
from threading import Lock
from typing import Protocol

import torch
from transformers import AutoModelForSeq2SeqLM, NllbTokenizer

from .config import settings
from .languages import languages_db

MODEL_COMPILE = settings.model_compile
LANG_PATTERN = re.compile(r"^[a-z]{3}_[A-Z][a-z]{3}$")


class TranslationEngineProtocol(Protocol):
    """Protocol defining the interface for a translation engine."""

    model_name: str
    has_cuda: bool
    device: str
    tokenizer: NllbTokenizer
    languages: dict

    def validate_language(self, lang: str) -> None:
        """Validate languages are in model"""
        ...

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        """Translate text from source language to target language."""
        ...


class NllbTranslationEngine:
    def __init__(self, model_name: str):
        # Модель можно задать в переменной окружения
        self.model_path = os.path.join(settings.model_storage, model_name)
        self._lock = Lock()
        self.model_name = model_name

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found at {self.model_path}")

        self.has_cuda = torch.cuda.is_available()
        self.device = "cuda" if self.has_cuda else "cpu"

        if self.has_cuda:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

        self.tokenizer = NllbTokenizer.from_pretrained(self.model_path)

        model = AutoModelForSeq2SeqLM.from_pretrained(
            self.model_path,
            dtype=torch.float16 if self.has_cuda else torch.float32,
        ).to(self.device)

        # Чтобы не было конфликта между `max_new_tokens` and `max_length`, выставляем max_length = None
        model.generation_config.max_length = None
        model.eval()
        self.model = model

        # Поддерживаемые языки обогащаем из локальной БД
        self.languages = dict(
            [
                (lang_code, languages_db.get(lang_code))
                for lang_code in self._get_supported_languages()
            ]
        )

    def _get_supported_languages(self) -> list[str]:
        """Возвращает список языков, имеющихся в модели (только коды в формате nllb)"""
        langs = [
            token
            for token in self.tokenizer.all_special_tokens
            if LANG_PATTERN.match(token)
        ]
        return sorted(langs)

    def validate_language(self, lang: str) -> None:
        if self.languages.get(lang) is None:
            raise ValueError(f"Unknown language: ${lang=}")

    @torch.inference_mode()
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        """Translate a single chunk of text from source language to target language.

        Args:
            text: A single chunk of text to translate (already segmented).
            src_lang: Source language code (e.g., 'eng_Latn').
            tgt_lang: Target language code (e.g., 'rus_Cyrl').

        Returns:
            Translated text chunk.

        Note:
            This method expects pre-segmented text. Use PlainTextTranslator or
            MarkdownTranslator for full document translation with segmentation.
        """
        translated = ""

        with self._lock:
            self.tokenizer.src_lang = src_lang
            forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(tgt_lang)

            text_stripped = text.strip()
            if not text_stripped:
                return text

            inputs = self.tokenizer(
                text_stripped,
                return_tensors="pt",
                truncation=True,
                max_length=settings.tokenizer_max_length,
            ).to(self.device)

            tokens = self.model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                max_new_tokens=settings.max_new_tokens,
                use_cache=True,
            )
            translated = self.tokenizer.batch_decode(tokens, skip_special_tokens=True)[
                0
            ]

            # Restore leading/trailing whitespace if present in original
            if text and translated:
                if text[0].isspace() and not translated[0].isspace():
                    translated = " " + translated.lstrip()
                if text[-1].isspace() and not translated[-1].isspace():
                    translated = translated.rstrip() + " "

        return translated
