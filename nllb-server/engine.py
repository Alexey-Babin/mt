import os
import re
from threading import Lock

import torch
from transformers import AutoModelForSeq2SeqLM, NllbTokenizer

MODEL_COMPILE = os.environ.get("MT_MODEL_COMPILE", "0") == "1"
LANG_PATTERN = re.compile(r"^[a-z]{3}_[A-Z][a-z]{3}$")


class Translator:
    def __init__(self, path_to_model):
        self._lock = Lock()
        self.model_name = path_to_model.split("/")[-1]
        self.model_path = path_to_model

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
        model.eval()
        self.model = model

    @torch.inference_mode()
    def translate(self, text, src_lang, tgt_lang):
        with self._lock:
            self.tokenizer.src_lang = src_lang
            inputs = self.tokenizer(text, return_tensors="pt").to(self.device)

            forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(tgt_lang)

            tokens = self.model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                max_new_tokens=256,
                use_cache=True,
            )
            return self.tokenizer.batch_decode(tokens, skip_special_tokens=True)[0]

    def get_supported_languages(self):
        langs = [
            token
            for token in self.tokenizer.all_special_tokens
            if LANG_PATTERN.match(token)
        ]
        return sorted(langs)
