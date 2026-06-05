---
name: debugging-markdown-translation-tests
description: Debug failing markdown translation tests by tracing buffer state, AST walk output, and reconstruction spacing
source: auto-skill
extracted_at: '2026-06-03T10:35:11.018Z'
---

# Debugging Markdown Translation Tests

When markdown translation tests fail (especially "not translated" errors), the issue is often in the test's `translation_dict` not matching the actual format of `extracted_text` produced by the AST walker.

## Common Root Causes

1. **Wrong placeholder format**: After Phase 0d, all placeholders use dunder format with single-letter codes
   - Strong → `__B_O_1__` / `__B_C_1__`, Link → `__L_O_1__` / `__L_C_1__`, Code → `__C_1__`
   - Code mapping is in `models/placeholder_codes.py` (PAIRED_CODES, SINGLE_TRANSLATE_CODES, PROTECT_CODES)
   - Task-list checkboxes use code `T`: `__T_1__`

2. **Wrong placeholder ID**: `PlaceholderManager` uses an incrementing counter, so IDs depend on the order of inline elements in the document
   - Example: If a paragraph has `__B_O_1__` (strong) first, then a link gets `__L_O_2__`, not `__L_O_1__`
   - Always verify the exact ID from debug output, don't assume

3. **Placeholder spacing is critical**: All placeholders are space-separated from surrounding text by `InlineCollector._append_tag()`
   - Format: `"This is __B_O_1__ bold __B_C_1__  text."` (spaces around every placeholder)
   - **Test translation_dict keys MUST include spaces around placeholders** — exact match required
   - Double spaces can occur (e.g., `__B_C_1__  text`) because `_append_tag` adds a trailing space and the next text starts with a space

4. **Sentence splitting**: `split_sentences()` breaks text into segments that must match the test dictionary exactly
   - A paragraph like "This is **bold** text. Go to [Google](https://google.com)." becomes two segments:
     - `"This is __B_O_1__ bold __B_C_1__  text."`
     - `"Go to __L_O_2__ Google __L_C_2__ ."`
   - The mock engine does exact matching per segment, so test dictionaries must match these splits
   - **Always add both individual segments AND the full joined sentence** to `integration_translation_dict` (as fallback)

5. **Placeholder restoration issues**: `PlaceholderRestorer.normalize_text()` handles post-NLLB cleanup
   - Uses `_PLACEHOLDER_PUNCTUATION_RE` to strip space between closing/atomic tags and punctuation: `__L_C_1__ .` → `__L_C_1__.`
   - Collapses multiple spaces: `re.sub(r"  +", " ", ...)`
   - Check `src/mt_server/markdown2/reconstructor/placeholder_restorer.py` for current normalization logic

6. **Reconstruction spacing**: Different block types require different newline handling
   - Front matter needs `\n\n` after closing `---`
   - Headings at root level need double newline (not single)
   - **Top-level lists/tables** need double newline after closing (`ensure_double_newline()`)
   - **Nested lists** need only single newline (check `stack_size == 0` before adding double newline)
   - Check `src/mt_server/markdown2/reconstructor/main.py` for `_handle_structural_close` and `_handle_table_structure` logic

7. **Code blocks are NOT translated**: Fence/code_block/math_block have `need_translation=False` in AST walker
   - Test expectations must preserve original code content
   - Comments in code are not translated

8. **Code block handler duplication bug**: `code_block_handler.handle_fence()` can write duplicate content if:
   - Opening fence marker is written without prefix when prefix is needed
   - Check that all three writes (open fence, code lines, close fence) use the same prefix logic

## Debugging Procedure

1. **Run the test with verbose logging** to see the pipeline stages:
   ```bash
   cd /opt/mt/nllb-server && uv run pytest tests/markdown2/<test_file.py>::<TestClass>::<test_name> -v -s 2>&1
   ```

2. **Add diagnostic logging to trace buffer state** at key reconstruction points:
   - In `block_writer.py:write_with_prefix()` - log `line_prefix`, `item_marker`, and buffer tail
   - In `reconstructor/main.py:_handle_structural_close()` - log buffer after closing lists/tables
   - In `reconstructor/main.py:_handle_table_structure()` - log buffer after table_close
   - This reveals exactly what's being written and when spacing issues occur

3. **Inspect the full buffer output**:
   ```bash
   uv run pytest tests/markdown2/<test>.py::<test_name> -v -s --log-cli-level=DEBUG 2>&1 | grep "FULL BUFFER" -A 1
   ```
   Compare the `repr()` output with expected markdown to spot missing `\n` or extra content.

4. **Check chunker input and merge output** to verify translation flow:
   ```bash
   uv run pytest tests/markdown2/<test>.py::<test_name> -v -s --log-cli-level=DEBUG 2>&1 | grep -E "(CHUNKER:|MERGE:)"
   ```
   - `CHUNKER:` shows what text is sent for translation (verify placeholders match test dict)
   - `MERGE:` shows what translations are applied back

5. **Create a standalone debug script** to inspect the actual AST walk output:
   ```python
   from mt_server.markdown2.parser import create_markdown_parser
   from markdown_it.tree import SyntaxTreeNode
   from mt_server.markdown2.ast_walker import ASTWalker

   parser = create_markdown_parser()
   tokens = parser.parse('<your_test_markdown>')
   root = SyntaxTreeNode(tokens)

   walker = ASTWalker()
   units = walker.walk(root)

   for u in units:
       if u.need_translation and u.extracted_text.strip():
           print(f'  "{u.extracted_text}": "PLACEHOLDER",')
   ```
   Use this output to build exact `translation_dict` entries for tests. The `extracted_text` will contain placeholders with spaces around them (e.g., `"This is __B_O_1__ bold __B_C_1__  text."`).

6. **Match the exact format** in your test's `translation_dict`:
   - Use the exact placeholder prefix shown in the debug output
   - Include any whitespace that appears between placeholders and text
   - The mock engine does exact string matching on segments
   - **Code blocks**: Don't add translations for code content (it's not translated)
   - **Fence syntax**: All lines must have `>` prefix when inside blockquote

## Key Files

- `src/mt_server/markdown2/models/placeholder_codes.py` - Centralized placeholder code mapping (B, I, L, C, etc.) and SEGMENT_SEPARATOR
- `src/mt_server/markdown2/models/placeholder.py` - `Placeholder` dataclass + `PlaceholderManager`
- `src/mt_server/markdown2/ast_walker/handlers/inline_collector.py` - How `extracted_text` is built (includes `_append_tag()` for space-guaranteeing)
- `src/mt_server/markdown2/reconstructor/placeholder_restorer.py` - Restoration + `normalize_text()` with `_PLACEHOLDER_PUNCTUATION_RE`
- `src/mt_server/markdown2/reconstructor/main.py` - Spacing logic for lists/tables
- `src/mt_server/markdown2/reconstructor/block_writer.py` - Buffer write operations with prefixes
- `src/mt_server/markdown2/reconstructor/code_block_handler.py` - Fence/code block rendering
- `src/mt_server/markdown2/chunker.py` - Text chunking and translation merging (uses `SEGMENT_SEPARATOR`)
- `tests/markdown2/conftest.py` - Mock translation engine implementation
- `tests/markdown2/test_markdown_elements.py` - Includes `TestPlaceholderSpacing` regression tests
