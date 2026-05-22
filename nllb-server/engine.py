import os
import re
from threading import Lock

import torch
from config import config
from languages import LanguageRecord, languages_db
from markdown_utils import detect_markdown, translate_markdown
from transformers import AutoModelForSeq2SeqLM, NllbTokenizer
from utils import split_into_chunks

MODEL_COMPILE = config.model_compile
LANG_PATTERN = re.compile(r"^[a-z]{3}_[A-Z][a-z]{3}$")


class Translator:
    def __init__(self, path_to_model):
        self._lock = Lock()
        self.model_name = path_to_model.split("/")[-1]
        self.model_path = path_to_model
        self._languages: dict[str, LanguageRecord | None] | None = None

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

        # Чтобы не было конфликта между `max_new_tokens` and `max_length`
        model.generation_config.max_length = None
        model.eval()
        self.model = model

    @property
    def languages(self) -> dict[str, LanguageRecord | None]:
        """NLLB language codes enriched with display metadata from languages_db.

        Returns a dict mapping each NLLB language code (e.g. ``"ace_Latn"``) to its
        metadata record from ``languages.json``, or ``None`` if the code is unknown.
        The result is computed once and cached.
        """
        if self._languages is None:
            self._languages = {
                code: languages_db.get(code) for code in self.get_supported_languages()
            }
        return self._languages

    def get_supported_languages(self):
        """Возвращает список языков, имеющихся в модели (только коды в формате nllb)"""
        langs = [
            token
            for token in self.tokenizer.all_special_tokens
            if LANG_PATTERN.match(token)
        ]
        return sorted(langs)

    @torch.inference_mode()
    def translate(self, text, src_lang, tgt_lang):
        # Detect if input is markdown and use appropriate translation flow
        if detect_markdown(text):
            return self._translate_markdown(text, src_lang, tgt_lang)
        else:
            return self._translate_plain_text(text, src_lang, tgt_lang)

    def _translate_markdown(self, text, src_lang, tgt_lang):
        """Translate markdown text while preserving formatting."""
        with self._lock:
            self.tokenizer.src_lang = src_lang
            return translate_markdown(
                text=text,
                tokenizer=self.tokenizer,
                model=self.model,
                src_lang=src_lang,
                tgt_lang=tgt_lang,
            )

    def _translate_plain_text(self, text, src_lang, tgt_lang):
        """Translate plain text using the original chunking approach."""
        chunks = split_into_chunks(
            tokenizer=self.tokenizer, text=text, nllb_lang_code=src_lang
        )
        translated_chunks = []

        with self._lock:
            self.tokenizer.src_lang = src_lang
            forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(tgt_lang)

            for chunk in chunks:
                inputs = self.tokenizer(
                    chunk.text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=config.tokenizer_max_length,
                ).to(self.device)

                tokens = self.model.generate(
                    **inputs,
                    forced_bos_token_id=forced_bos_token_id,
                    max_new_tokens=config.max_new_tokens,
                    use_cache=True,
                )
                translated = self.tokenizer.batch_decode(
                    tokens, skip_special_tokens=True
                )[0]
                translated_chunks.append((chunk.block_ix, translated))

        blocks = {}
        for block_index, translated in translated_chunks:
            blocks.setdefault(block_index, []).append(translated)
        result = []
        for block_ix in sorted(blocks):
            result.append(" ".join(blocks[block_ix]))

        return "\n\n".join(result)
