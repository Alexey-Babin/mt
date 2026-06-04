"""Unit tests for PlainTextTranslator."""

from unittest.mock import Mock, call

import pytest

from mt_server.plain_text_translator import PlainTextTranslator
from mt_server.utils import TranslationChunk


class TestPlainTextTranslator:
    """Tests for PlainTextTranslator class."""

    def test_init(self):
        """Test translator initialization."""
        engine = Mock()
        translator = PlainTextTranslator(
            text="Hello world",
            src_lang="eng_Latn",
            target_lang="rus_Cyrl",
            engine=engine,
        )

        assert translator.text == "Hello world"
        assert translator.src_lang == "eng_Latn"
        assert translator.target_lang == "rus_Cyrl"
        assert translator.engine is engine

    def test_process_empty_text(self):
        """Test translation of empty text."""
        engine = Mock()
        translator = PlainTextTranslator(
            text="",
            src_lang="eng_Latn",
            target_lang="rus_Cyrl",
            engine=engine,
        )

        result = translator.process()

        assert result == ""
        engine.translate.assert_not_called()

    def test_process_whitespace_only(self):
        """Test translation of whitespace-only text."""
        engine = Mock()
        translator = PlainTextTranslator(
            text="   \n  ",
            src_lang="eng_Latn",
            target_lang="rus_Cyrl",
            engine=engine,
        )

        result = translator.process()

        assert result == "   \n  "
        engine.translate.assert_not_called()

    def test_process_single_chunk(self):
        """Test translation of text that fits in a single chunk."""
        engine = Mock()
        engine.tokenizer = Mock()
        engine.translate.return_value = "Привет мир"

        # Mock split_into_chunks to return a single chunk
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "mt_server.plain_text_translator.split_into_chunks",
                lambda tokenizer, text, nllb_lang_code: [
                    TranslationChunk(
                        text="Hello world",
                        tokens=5,
                        sentences=1,
                        block_ix=0,
                    )
                ],
            )

            translator = PlainTextTranslator(
                text="Hello world",
                src_lang="eng_Latn",
                target_lang="rus_Cyrl",
                engine=engine,
            )

            result = translator.process()

            assert result == "Привет мир"
            engine.translate.assert_called_once_with(
                text="Hello world",
                src_lang="eng_Latn",
                tgt_lang="rus_Cyrl",
            )

    def test_process_multiple_chunks(self):
        """Test translation of text split into multiple chunks."""
        engine = Mock()
        engine.tokenizer = Mock()
        engine.translate.side_effect = ["Привет", "мир", "как дела"]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "mt_server.plain_text_translator.split_into_chunks",
                lambda tokenizer, text, nllb_lang_code: [
                    TranslationChunk(text="Hello", tokens=2, sentences=1, block_ix=0),
                    TranslationChunk(text="world", tokens=2, sentences=1, block_ix=0),
                    TranslationChunk(
                        text="How are you", tokens=4, sentences=1, block_ix=0
                    ),
                ],
            )

            translator = PlainTextTranslator(
                text="Hello world How are you",
                src_lang="eng_Latn",
                target_lang="rus_Cyrl",
                engine=engine,
            )

            result = translator.process()

            assert result == "Привет мир как дела"
            assert engine.translate.call_count == 3

    def test_process_preserves_spaces_between_chunks(self):
        """Test that spaces are preserved between translated chunks."""
        engine = Mock()
        engine.tokenizer = Mock()
        engine.translate.side_effect = ["Первый", "Второй"]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "mt_server.plain_text_translator.split_into_chunks",
                lambda tokenizer, text, nllb_lang_code: [
                    TranslationChunk(
                        text="First sentence.", tokens=5, sentences=1, block_ix=0
                    ),
                    TranslationChunk(
                        text="Second sentence.", tokens=5, sentences=1, block_ix=0
                    ),
                ],
            )

            translator = PlainTextTranslator(
                text="First sentence. Second sentence.",
                src_lang="eng_Latn",
                target_lang="rus_Cyrl",
                engine=engine,
            )

            result = translator.process()

            # Chunks are joined with spaces
            assert result == "Первый Второй"

    def test_process_calls_engine_with_correct_params(self):
        """Test that engine is called with correct parameters for each chunk."""
        engine = Mock()
        engine.tokenizer = Mock()
        engine.translate.return_value = "translated"

        chunks_data = [
            ("Chunk one", 5, 1, 0),
            ("Chunk two", 5, 1, 0),
        ]

        def mock_split_into_chunks(tokenizer, text, nllb_lang_code):
            return [
                TranslationChunk(text=t, tokens=tok, sentences=s, block_ix=b)
                for t, tok, s, b in chunks_data
            ]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "mt_server.plain_text_translator.split_into_chunks",
                mock_split_into_chunks,
            )

            translator = PlainTextTranslator(
                text="Source text",
                src_lang="fra_Latn",
                target_lang="deu_Latn",
                engine=engine,
            )

            result = translator.process()

            # Verify result is correctly joined
            assert result == "translated translated"

            # Verify translate was called with correct params for each chunk
            expected_calls = [
                call(text="Chunk one", src_lang="fra_Latn", tgt_lang="deu_Latn"),
                call(text="Chunk two", src_lang="fra_Latn", tgt_lang="deu_Latn"),
            ]
            engine.translate.assert_has_calls(expected_calls)
            assert engine.translate.call_count == 2
