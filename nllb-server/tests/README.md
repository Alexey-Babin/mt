# Tests for NLLB Translation Server

This directory contains comprehensive tests for the NLLB Translation Server application.

## Test Structure

```
tests/
├── api/              # FastAPI endpoint tests
├── service/          # Translation service tests
├── languages/        # Languages module tests
├── utils/            # Utility functions tests
├── markdown/         # Markdown processing tests
├── conftest.py       # Common fixtures and configuration
└── __init__.py
```

## Test Coverage

### API Tests (`tests/api/`)

Tests for FastAPI endpoints defined in `main.py`:

- **`/translate` endpoint**
  - Successful translation request
  - Empty text validation (400 error)
  - Service not ready (503 error)
  - Internal translation error (500 error)
  - Different format values (auto, plain, markdown)

- **`/health` endpoint**
  - Service ready status
  - Service loading status

- **`/languages` endpoint**
  - Members only language level
  - Former members language level
  - All languages level
  - Default language level

### Service Tests (`tests/service/`)

Tests for `translation_service.py`:

- **TranslationService class**
  - Plain text translation
  - Empty text handling
  - Whitespace-only text handling
  - Auto-detection of plain text format
  - Auto-detection of markdown format
  - Markdown format handling (with fallback)
  - Format resolution (explicit, auto, none, unknown)

- **Format Detection**
  - Empty text detection
  - Plain text detection
  - Code blocks detection
  - Headings detection
  - Links detection
  - Bold text detection
  - Inline code detection
  - Bullets detection
  - Numbered list detection
  - Blockquote detection
  - Table detection

### Languages Tests (`tests/languages/`)

Tests for `languages.py`:

- **read_languages_db function**
  - Successful reading
  - Empty file handling
  - Invalid JSON handling
  - Correct file path usage

- **languages_db fixture**
  - Dictionary structure
  - Expected language keys
  - Language record structure

- **LanguageRecord TypedDict**
  - Field validation

### Utils Tests (`tests/utils/`)

Tests for `utils.py`:

- **split_blocks function**
  - Simple block splitting
  - Multiple newlines handling
  - Whitespace handling
  - Empty input handling
  - No blank lines handling

- **split_sentences function**
  - Simple sentence splitting
  - Leading space preservation
  - Empty text handling
  - Single sentence handling

- **count_tokens function**
  - Simple token counting
  - Empty text handling
  - Tokenizer call verification

- **split_long_sentence function**
  - Long sentence splitting
  - Empty sentence handling
  - Short sentence handling
  - Word preservation

- **split_into_chunks function**
  - Simple chunk splitting
  - Empty text handling
  - Chunk structure verification
  - Max token limit respect
  - Block preservation

- **get_segmenter function**
  - Caching behavior
  - Different languages
  - Fallback to English

## Running Tests

```bash
# Run all tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/api/test_main.py

# Run with verbose output
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=src/mt_server --cov-report=html
```

## Test Fixtures

Common fixtures are defined in `conftest.py`:

- `mock_translator` - Mock translator engine
- `translation_service` - TranslationService instance
- `mock_tokenizer` - Mock tokenizer
- `mock_segmenter` - Mock segmenter
- `sample_text` - Sample text for testing
- `sample_markdown` - Sample markdown text
- `sample_blocks` - Sample text with multiple blocks
