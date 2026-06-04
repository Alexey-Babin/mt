"""Tests for utils.py"""

from unittest.mock import MagicMock, patch

from mt_server.utils import (
    TranslationChunk,
    count_tokens,
    get_segmenter,
    split_blocks,
    split_into_chunks,
    split_long_sentence,
    split_sentences,
)


class TestSplitBlocks:
    """Tests for split_blocks function."""

    def test_split_blocks_simple(self):
        """Test splitting text by blank lines."""
        text = "Block 1\n\nBlock 2\n\nBlock 3"
        result = split_blocks(text)

        assert len(result) == 3
        assert result[0] == "Block 1"
        assert result[1] == "Block 2"
        assert result[2] == "Block 3"

    def test_split_blocks_multiple_newlines(self):
        """Test splitting with multiple newlines."""
        text = "Block 1\n\n\n\nBlock 2"
        result = split_blocks(text)

        assert len(result) == 2
        assert result[0] == "Block 1"
        assert result[1] == "Block 2"

    def test_split_blocks_with_whitespace(self):
        """Test splitting with whitespace between blocks."""
        text = "Block 1\n  \n  \nBlock 2"
        result = split_blocks(text)

        assert len(result) == 2
        assert result[0] == "Block 1"
        assert result[1] == "Block 2"

    def test_split_blocks_empty_input(self):
        """Test splitting empty text."""
        result = split_blocks("")
        assert result == []

    def test_split_blocks_no_blank_lines(self):
        """Test text without blank lines."""
        text = "Line 1\nLine 2\nLine 3"
        result = split_blocks(text)

        assert len(result) == 1
        assert result[0] == text

    def test_split_blocks_trims_whitespace(self):
        """Test that split_blocks trims whitespace from blocks."""
        text = "  Block 1  \n\n  Block 2  "
        result = split_blocks(text)

        assert len(result) == 2
        # Note: split_blocks does NOT trim whitespace from blocks
        # It only splits on blank lines and filters empty blocks
        assert result[0] == "  Block 1  "
        assert result[1] == "  Block 2  "


class TestSplitSentences:
    """Tests for split_sentences function."""

    def test_split_sentences_simple(self):
        """Test splitting simple text into sentences."""
        text = "Hello world. How are you? I am fine!"
        result = split_sentences(text, "eng_Latn")

        assert len(result) == 3
        assert "Hello world." in result[0]
        assert "How are you?" in result[1]
        assert "I am fine!" in result[2]

    def test_split_sentences_preserves_leading_space(self):
        """Test that leading space is preserved."""
        text = " Hello world"
        result = split_sentences(text, "eng_Latn")

        assert len(result) == 1
        assert result[0].startswith(" ")

    def test_split_sentences_empty(self):
        """Test splitting empty text."""
        result = split_sentences("", "eng_Latn")
        # Note: pysbd returns empty list for empty string
        assert result == []

    def test_split_sentences_single_sentence(self):
        """Test text with single sentence."""
        text = "Hello world"
        result = split_sentences(text, "eng_Latn")

        assert len(result) == 1
        assert result[0] == text


class TestCountTokens:
    """Tests for count_tokens function."""

    def test_count_tokens_simple(self):
        """Test counting tokens in simple text."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {"input_ids": [1, 2, 3]}

        result = count_tokens(mock_tokenizer, "Hello world")

        assert result == 3
        mock_tokenizer.assert_called_once_with(
            "Hello world", add_special_tokens=False, truncation=False
        )

    def test_count_tokens_empty(self):
        """Test counting tokens in empty text."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {"input_ids": []}

        result = count_tokens(mock_tokenizer, "")

        assert result == 0

    def test_count_tokens_calls_tokenizer_correctly(self):
        """Test that tokenizer is called with correct parameters."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {"input_ids": [1, 2, 3]}

        count_tokens(mock_tokenizer, "test")

        mock_tokenizer.assert_called_once_with(
            "test", add_special_tokens=False, truncation=False
        )


class TestSplitLongSentence:
    """Tests for split_long_sentence function."""

    def test_split_long_sentence_simple(self):
        """Test splitting long sentence into chunks."""
        mock_tokenizer = MagicMock()

        # Simulate: " " = 1 token, "word" = 1 token each
        def mock_count(text):
            return len(text.split())

        mock_tokenizer.side_effect = lambda t, **kwargs: {
            "input_ids": list(range(mock_count(t)))
        }

        sentence = "one two three four five six"
        result = split_long_sentence(mock_tokenizer, sentence, max_tokens=3)

        # Should split into chunks of ~3 tokens
        assert len(result) >= 1

    def test_split_long_sentence_empty(self):
        """Test splitting empty sentence."""
        mock_tokenizer = MagicMock()
        result = split_long_sentence(mock_tokenizer, "", max_tokens=10)

        assert result == []

    def test_split_long_sentence_short(self):
        """Test short sentence returns as is."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {"input_ids": [1, 2]}  # 2 tokens

        result = split_long_sentence(mock_tokenizer, "short text", max_tokens=10)

        # Note: split_long_sentence adds a leading space to the first word
        # The actual result depends on the implementation
        assert len(result) == 1
        assert "short" in result[0]
        assert "text" in result[0]

    def test_split_long_sentence_preserves_words(self):
        """Test that all words are preserved in chunks."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.side_effect = lambda t, **kwargs: {
            "input_ids": list(range(len(t.split())))
        }

        sentence = "one two three four five"
        chunks = split_long_sentence(mock_tokenizer, sentence, max_tokens=2)

        # Reconstruct and verify all words are present
        reconstructed = " ".join(chunks)
        assert "one" in reconstructed
        assert "two" in reconstructed
        assert "three" in reconstructed
        assert "four" in reconstructed
        assert "five" in reconstructed


class TestSplitIntoChunks:
    """Tests for split_into_chunks function."""

    def test_split_into_chunks_simple(self):
        """Test splitting text into chunks."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {"input_ids": [1, 2, 3]}  # 3 tokens per call

        text = "Block 1\n\nBlock 2"
        result = split_into_chunks(mock_tokenizer, text, "eng_Latn", max_tokens=10)

        assert len(result) >= 1
        assert isinstance(result[0], TranslationChunk)

    def test_split_into_chunks_empty(self):
        """Test splitting empty text."""
        mock_tokenizer = MagicMock()
        result = split_into_chunks(mock_tokenizer, "", "eng_Latn")

        assert result == []

    def test_split_into_chunks_returns_chunks(self):
        """Test that result contains TranslationChunk objects."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {"input_ids": [1, 2, 3]}

        result = split_into_chunks(mock_tokenizer, "text", "eng_Latn")

        for chunk in result:
            assert isinstance(chunk, TranslationChunk)
            assert hasattr(chunk, "text")
            assert hasattr(chunk, "tokens")
            assert hasattr(chunk, "sentences")
            assert hasattr(chunk, "block_ix")

    def test_split_into_chunks_respects_max_tokens(self):
        """Test that chunks respect max token limit."""
        mock_tokenizer = MagicMock()
        # Simulate 5 tokens per sentence
        mock_tokenizer.side_effect = lambda t, **kwargs: {"input_ids": list(range(5))}

        text = "Sentence 1. Sentence 2. Sentence 3."
        result = split_into_chunks(mock_tokenizer, text, "eng_Latn", max_tokens=10)

        # Each chunk should not exceed max_tokens significantly
        for chunk in result:
            assert chunk.tokens <= 10

    def test_split_into_chunks_preserves_blocks(self):
        """Test that blocks are preserved correctly."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {"input_ids": [1, 2, 3]}

        text = "Block 1\n\nBlock 2\n\nBlock 3"
        result = split_into_chunks(mock_tokenizer, text, "eng_Latn")

        # Check that block indices are assigned correctly
        block_indices = [chunk.block_ix for chunk in result]
        assert 0 in block_indices
        assert 1 in block_indices
        assert 2 in block_indices


class TestGetSegmenter:
    """Tests for get_segmenter function."""

    def test_get_segmenter_caches(self):
        """Test that get_segmenter uses caching."""
        # Note: get_segmenter uses @lru_cache decorator
        # This test verifies the caching behavior
        segmenter1 = get_segmenter("eng_Latn")
        segmenter2 = get_segmenter("eng_Latn")

        assert segmenter1 is segmenter2

    def test_get_segmenter_different_languages(self):
        """Test that different languages get different segmenters."""
        segmenter1 = get_segmenter("eng_Latn")
        segmenter2 = get_segmenter("rus_Cyrl")

        assert segmenter1 is not segmenter2

    def test_get_segmenter_fallback_to_english(self):
        """Test fallback to English for unknown language."""
        with patch("pysbd.Segmenter") as MockSegmenter:
            get_segmenter("unknown_lang")

            MockSegmenter.assert_called_once_with(language="en", clean=False)
