"""Tests for translation_service.py"""

from unittest.mock import MagicMock, patch

import pytest

from mt_server.format_detection import looks_like_markdown
from mt_server.translation_service import TextFormat, TranslationService


@pytest.fixture
def mock_engine():
    """Create a mock translation engine."""
    engine = MagicMock()
    engine.translate = MagicMock(return_value="Translated text")
    engine.tokenizer = MagicMock()
    return engine


class TestTranslationService:
    """Tests for TranslationService class."""

    def test_translate_plain_text(self, mock_engine):
        """Test translation of plain text."""
        service = TranslationService(mock_engine)
        with patch(
            "mt_server.plain_text_translator.PlainTextTranslator"
        ) as MockTranslator:
            mock_translator = MagicMock()
            mock_translator.process.return_value = "Translated text"
            MockTranslator.return_value = mock_translator

            result = service.translate(
                text="Hello world",
                src_lang="eng_Latn",
                tgt_lang="rus_Cyrl",
                format=TextFormat.PLAIN,
            )

            assert result == "Translated text"
            MockTranslator.assert_called_once_with(
                text="Hello world",
                src_lang="eng_Latn",
                target_lang="rus_Cyrl",
                engine=mock_engine,
            )
            mock_translator.process.assert_called_once()

    def test_translate_empty_text(self, mock_engine):
        """Test translation of empty text returns empty string."""
        service = TranslationService(mock_engine)

        result = service.translate(
            text="",
            src_lang="eng_Latn",
            tgt_lang="rus_Cyrl",
        )

        assert result == ""
        # No translator should be created for empty text
        mock_engine.translate.assert_not_called()

    def test_translate_whitespace_only_text(self, mock_engine):
        """Test translation of whitespace-only text returns original."""
        service = TranslationService(mock_engine)

        result = service.translate(
            text="   ",
            src_lang="eng_Latn",
            tgt_lang="rus_Cyrl",
        )

        assert result == "   "
        mock_engine.translate.assert_not_called()

    def test_translate_auto_detect_plain(self, mock_engine):
        """Test auto-detection of plain text format."""
        service = TranslationService(mock_engine)

        with patch(
            "mt_server.plain_text_translator.PlainTextTranslator"
        ) as MockTranslator:
            mock_translator = MagicMock()
            mock_translator.process.return_value = "Translated text"
            MockTranslator.return_value = mock_translator

            result = service.translate(
                text="Hello world",
                src_lang="eng_Latn",
                tgt_lang="rus_Cyrl",
                format=TextFormat.AUTO,
            )

            assert result == "Translated text"
            MockTranslator.assert_called_once()
            mock_translator.process.assert_called_once()

    def test_translate_auto_detect_markdown(self, mock_engine):
        """Test auto-detection of markdown format."""
        service = TranslationService(mock_engine)

        with patch(
            "mt_server.markdown2.translator.MarkdownTranslator"
        ) as MockTranslator:
            mock_translator = MagicMock()
            mock_translator.process.return_value = "Translated markdown"
            MockTranslator.return_value = mock_translator

            result = service.translate(
                text="# Header\n\n**Bold text**",
                src_lang="eng_Latn",
                tgt_lang="rus_Cyrl",
                format=TextFormat.AUTO,
            )

            assert result == "Translated markdown"
            MockTranslator.assert_called_once()
            mock_translator.process.assert_called_once()

    def test_translate_fallback_on_markdown_error(self, mock_engine):
        """Test fallback to plain text on markdown error."""
        service = TranslationService(mock_engine)

        with patch(
            "mt_server.markdown2.translator.MarkdownTranslator"
        ) as MockMarkdownTranslator:
            MockMarkdownTranslator.side_effect = Exception("Markdown error")

            with patch(
                "mt_server.plain_text_translator.PlainTextTranslator"
            ) as MockPlainTranslator:
                mock_plain_translator = MagicMock()
                mock_plain_translator.process.return_value = "Fallback translated"
                MockPlainTranslator.return_value = mock_plain_translator

                result = service.translate(
                    text="# Header",
                    src_lang="eng_Latn",
                    tgt_lang="rus_Cyrl",
                    format=TextFormat.AUTO,  # Will detect as markdown
                )

                # Should fallback to plain text translation
                assert result == "Fallback translated"
                MockPlainTranslator.assert_called_once()
                mock_plain_translator.process.assert_called_once()

    def test_translate_with_explicit_markdown_format(self, mock_engine):
        """Test translation with explicit markdown format."""
        service = TranslationService(mock_engine)

        with patch(
            "mt_server.markdown2.translator.MarkdownTranslator"
        ) as MockTranslator:
            mock_translator = MagicMock()
            mock_translator.process.return_value = "Translated markdown"
            MockTranslator.return_value = mock_translator

            result = service.translate(
                text="# Header",
                src_lang="eng_Latn",
                tgt_lang="rus_Cyrl",
                format=TextFormat.MARKDOWN,
            )

            assert result == "Translated markdown"
            MockTranslator.assert_called_once()
            mock_translator.process.assert_called_once()

    def test_resolve_format_explicit_plain(self, mock_engine):
        """Test format resolution with explicit plain format."""
        service = TranslationService(mock_engine)

        result = service._resolve_format("Hello", TextFormat.PLAIN)

        assert result == TextFormat.PLAIN

    def test_resolve_format_explicit_markdown(self, mock_engine):
        """Test format resolution with explicit markdown format."""
        service = TranslationService(mock_engine)

        result = service._resolve_format("Hello", TextFormat.MARKDOWN)

        assert result == TextFormat.MARKDOWN

    def test_resolve_format_auto_detect_plain(self, mock_engine):
        """Test auto-detection of plain text."""
        service = TranslationService(mock_engine)

        result = service._resolve_format("Hello world", TextFormat.AUTO)

        assert result == TextFormat.PLAIN

    def test_resolve_format_auto_detect_markdown(self, mock_engine):
        """Test auto-detection of markdown text."""
        service = TranslationService(mock_engine)

        result = service._resolve_format("# Header", TextFormat.AUTO)

        assert result == TextFormat.MARKDOWN

    def test_resolve_format_none(self, mock_engine):
        """Test format resolution with None format."""
        service = TranslationService(mock_engine)

        result = service._resolve_format("Hello", None)

        assert result == TextFormat.PLAIN

    def test_resolve_format_unknown(self, mock_engine):
        """Test format resolution with unknown format (via type: ignore)."""
        service = TranslationService(mock_engine)

        # Using type: ignore because we're testing edge case with invalid format
        result = service._resolve_format("Hello", "unknown")  # type: ignore

        assert result == TextFormat.PLAIN


class TestFormatDetection:
    """Tests for format detection utilities."""

    def test_looks_like_markdown_empty(self):
        """Test empty text is not markdown."""
        assert looks_like_markdown("") is False
        assert looks_like_markdown("   ") is False

    def test_looks_like_markdown_plain_text(self):
        """Test plain text is not markdown."""
        assert looks_like_markdown("Hello world") is False
        assert looks_like_markdown("This is plain text") is False

    def test_looks_like_markdown_code_blocks(self):
        """Test text with code blocks is markdown."""
        assert looks_like_markdown("```\ncode\n```") is True

    def test_looks_like_markdown_headings(self):
        """Test text with headings is markdown."""
        assert looks_like_markdown("# Header") is True
        assert looks_like_markdown("## Subheader") is True
        assert looks_like_markdown("### Sub-subheader") is True

    def test_looks_like_markdown_links(self):
        """Test text with links is markdown."""
        assert looks_like_markdown("[link](http://example.com)") is True

    def test_looks_like_markdown_bold(self):
        """Test text with bold is markdown."""
        assert looks_like_markdown("**bold text**") is True
        # Note: __bold__ is not detected by current patterns (only **bold**)

    def test_looks_like_markdown_inline_code(self):
        """Test text with inline code is markdown."""
        assert looks_like_markdown("`code`") is True

    def test_looks_like_markdown_bullets(self):
        """Test text with bullets is markdown."""
        assert looks_like_markdown("- item") is True
        assert looks_like_markdown("* item") is True
        assert looks_like_markdown("+ item") is True

    def test_looks_like_markdown_numbered_list(self):
        """Test text with numbered list is markdown."""
        assert looks_like_markdown("1. item") is True
        assert looks_like_markdown("2. item") is True

    def test_looks_like_markdown_blockquote(self):
        """Test text with blockquote is markdown."""
        assert looks_like_markdown("> quote") is True

    def test_looks_like_markdown_table(self):
        """Test text with table is markdown."""
        assert looks_like_markdown("| col1 | col2 |") is True
        assert looks_like_markdown("| --- | --- |") is True
