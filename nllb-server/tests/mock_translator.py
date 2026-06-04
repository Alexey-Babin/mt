"""
Mock Translation Engine for testing.

This module provides a mock implementation of the TranslationEngineProtocol
that can be used for testing without requiring the actual NLLB model.

The mock only handles plain text translation. Code blocks, inline code,
and HTML tags are protected by placeholders.py before this method is called,
so they appear as opaque tokens here.
"""


class MockTokenizer:
    """Заглушка токенизатора для соответствия протоколу."""

    pass


class MockTranslationEngine:
    """Mock translation engine for testing purposes."""

    model_name: str = "mock-nllb-model"
    tokenizer: object

    def __init__(self, model_name=None):
        """Initialize mock translator.

        Args:
            model_name: Ignored in mock mode, kept for API compatibility.
        """
        self.has_cuda = False
        self.device = "cpu"
        self.tokenizer = MockTokenizer()

        # Supported languages for mock mode
        self.languages = {
            "eng_Latn": "English",
            "rus_Cyrl": "Russian",
            "deu_Latn": "German",
            "fra_Latn": "French",
            "spa_Latn": "Spanish",
        }

        # Pre-defined translations for test phrases
        self._translation_dict = {
            "Some text before.": "Некоторый текст перед.",
            "Content here.": "Контент здесь.",
            "This is a ": "Это ",
            " and another ": " и другой ",
            "Example Site": "Сайт Пример",
            "Test Reference": "Тестовая Ссылка",
            "HTML content": "HTML контент",
            "bold ": "смелый ",
            " text": " текст",
            "item ": "элемент ",
            "Use ": "Используйте ",
            ".": ".",
            "Bold ": "Жирный ",
            " text**": " текст**",
            "title: Test": "title: Test",
            "Hello": "Привет",
            "world": "мир",
            "Test": "Тест",
            "Code example": "Пример кода",
            "Python code": "код Python",
            "JavaScript code": "код JavaScript",
            "Some text after.": "Некоторый текст после.",
            "A paragraph.": "Параграф.",
            "Another paragraph.": "Другой параграф.",
            "List item": "Элемент списка",
            "Link text": "Текст ссылки",
            "Image alt": "Альтернативный текст",
        }

    def get_supported_languages(self):
        """Return list of supported language codes for mock mode."""
        return ["eng_Latn", "rus_Cyrl", "deu_Latn", "fra_Latn", "spa_Latn"]

    def translate(self, text, src_lang, tgt_lang):
        """
        Mock implementation for testing.

        This mock only handles plain text translation.
        Code blocks, inline code, and HTML tags are protected by placeholders.py
        before this method is called, so they appear as opaque tokens here.

        For known test phrases, returns predefined Russian translations.
        For unknown text, returns the original text unchanged.

        Args:
            text: Text to translate (with placeholders for protected content).
            src_lang: Source language code (ignored in mock).
            tgt_lang: Target language code (ignored in mock).

        Returns:
            Translated text with known phrases replaced.
        """
        # Check if the entire text matches a known phrase
        if text in self._translation_dict:
            return self._translation_dict[text]

        # Try to find and replace known substrings
        result = text
        for src, tgt in self._translation_dict.items():
            if src in result:
                result = result.replace(src, tgt)

        return result

    def validate_language(self, lang: str) -> None:
        pass
