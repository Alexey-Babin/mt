from os import path

import torch
from transformers import AutoModelForSeq2SeqLM, NllbTokenizer


class Translator:
    def __init__(self, path_to_model):

        self.model_name = path_to_model.split("/")[-1]
        self.model_path = path_to_model

        if not path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found at {self.model_path}")

        self.has_cuda = torch.cuda.is_available()
        self.device = "cuda" if self.has_cuda else "cpu"

        self.tokenizer = NllbTokenizer.from_pretrained(self.model_path)

        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            self.model_path,
            dtype=torch.float16 if self.has_cuda else torch.float32,
        ).to(self.device)

    @torch.inference_mode()
    def translate(self, text, src, tgt):
        self.tokenizer.src_lang = src
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(tgt)

        tokens = self.model.generate(
            **inputs,
            forced_bos_token_id=forced_bos_token_id,
            max_length=512,
        )
        return self.tokenizer.batch_decode(tokens, skip_special_tokens=True)[0]

    def get_supported_languages(self):
        langs = [
            token
            for token in self.tokenizer.additional_special_tokens
            if len(token) == 8 and "_" in token
        ]
        return sorted(langs)
