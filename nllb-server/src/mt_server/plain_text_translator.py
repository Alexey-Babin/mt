"""Plain text translator implementation.

This module provides the PlainTextTranslator class that implements
the TranslatorProtocol for plain text translation with segmentation.
"""

from mt_server.engine import TranslationEngineProtocol
from mt_server.utils import split_into_chunks


class PlainTextTranslator:
    """Translator for plain text with automatic segmentation.

    This translator handles plain text by splitting it into chunks
    based on sentences and blocks, translating each chunk separately,
    and then assembling the results.

    The translator is created per text to be translated and should not
    be reused for multiple texts.
    """

    def __init__(
        self,
        text: str,
        src_lang: str,
        target_lang: str,
        engine: TranslationEngineProtocol,
    ) -> None:
        """Initialize the plain text translator.

        Args:
            text: The source text to translate
            src_lang: Source language code (e.g., 'eng_Latn')
            target_lang: Target language code (e.g., 'rus_Cyrl')
            engine: Translation engine implementing TranslationEngineProtocol
        """
        self.text = text
        self.src_lang = src_lang
        self.target_lang = target_lang
        self.engine = engine

    def process(self) -> str:
        """Execute the full translation pipeline for plain text.

        Splits the text into chunks, translates each chunk via the engine,
        and assembles the results back into a single text.

        Returns:
            The translated text
        """
        if not self.text.strip():
            return self.text

        tokenizer = self.engine.tokenizer
        chunks = split_into_chunks(
            tokenizer=tokenizer,
            text=self.text,
            nllb_lang_code=self.src_lang,
        )

        translated_chunks = []
        for chunk in chunks:
            translated_chunk = self.engine.translate(
                text=chunk.text,
                src_lang=self.src_lang,
                tgt_lang=self.target_lang,
            )
            translated_chunks.append(translated_chunk)

        return " ".join(translated_chunks)
