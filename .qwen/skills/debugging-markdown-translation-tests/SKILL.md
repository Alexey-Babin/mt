---
name: debugging-markdown-translation-tests
description: Debug failing markdown translation tests by inspecting AST walk output and placeholder format
source: auto-skill
extracted_at: '2026-06-03T06:46:15.586Z'
---

# Debugging Markdown Translation Tests

When markdown translation tests fail (especially "not translated" errors), the issue is often in the test's `translation_dict` not matching the actual format of `extracted_text` produced by the AST walker.

## Common Root Causes

1. **Wrong placeholder prefix**: `PlaceholderManager` uses specific prefixes that may differ from the raw node type
   - Task-list checkboxes (`html_inline` nodes with `class="task-list-item-checkbox"`) use prefix `chk`, not `html`
   - See `src/mt_server/markdown2/placeholder.py:55-66` for the mapping

2. **Missing whitespace**: Text nodes from markdown-it include spaces between inline elements and text content
   - Example: `{chk_1} Done task` (with space) not `{chk_1}Done task`

## Debugging Procedure

1. **Run the test with verbose logging** to see the pipeline stages:
   ```bash
   cd /opt/mt/nllb-server && uv run pytest tests/markdown2/<test_file.py>::<TestClass>::<test_name> -v -s 2>&1
   ```

2. **Create a standalone debug script** to inspect the actual AST walk output:
   ```python
   from src.mt_server.markdown2.parser import create_markdown_parser
   from markdown_it.tree import SyntaxTreeNode
   from src.mt_server.markdown2.ast_walker import ASTWalker

   parser = create_markdown_parser()
   tokens = parser.parse('<your_test_markdown>')
   root = SyntaxTreeNode(tokens)

   walker = ASTWalker()
   units = walker.walk(root)

   for u in units:
       if u.need_translation:
           print(f'node_id={u.node_id}, extracted_text={repr(u.extracted_text)}')
           if u.placeholders:
               for ph in u.placeholders:
                   print(f'  placeholder: mask={ph.tag_mask!r}, strategy={ph.strategy}')
   ```

3. **Match the exact format** in your test's `translation_dict`:
   - Use the exact placeholder prefix shown in the debug output
   - Include any whitespace that appears between placeholders and text
   - The mock engine does exact string matching on segments

## Key Files

- `src/mt_server/markdown2/placeholder.py` - Placeholder generation logic and prefix mapping
- `src/mt_server/markdown2/handlers/inline_collector.py` - How `extracted_text` is built
- `tests/markdown2/conftest.py` - Mock translation engine implementation
