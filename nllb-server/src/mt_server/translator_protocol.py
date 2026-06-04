"""Protocol defining the interface for text translators.

Each translator implementation is created per text to be translated,
encapsulating the full translation pipeline for that specific text.
"""

from typing import Protocol


class TranslatorProtocol(Protocol):
    """Protocol for text translators.

    Each translator instance is created for a single text translation task.
    The translator encapsulates the full pipeline including segmentation,
    translation of chunks, and result assembly.

    Attributes:
        text: The source text to translate
        src_lang: Source language code
        target_lang: Target language code
        engine: Translation engine for translating individual chunks
    """

    def __init__(self, text: str, src_lang: str, target_lang: str, engine) -> None:
        """Initialize translator for a specific text.

        Args:
            text: The source text to translate
            src_lang: Source language code (e.g., 'eng_Latn')
            target_lang: Target language code (e.g., 'rus_Cyrl')
            engine: Translation engine implementing TranslationEngineProtocol
        """
        ...

    def process(self) -> str:
        """Execute the full translation pipeline.

        Returns:
            The translated text
        """
        ...
