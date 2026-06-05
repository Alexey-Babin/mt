---
name: refactoring-markdown2-module
description: Systematic approach to refactoring the markdown2 translation module with phased execution and test validation
source: auto-skill
extracted_at: '2026-06-04T12:58:07.116Z'
---

# Refactoring the markdown2 Module

When refactoring the `src/mt_server/markdown2/` module (or similar complex Python modules), follow a systematic phased approach to minimize risk and maintain test coverage throughout.

## Refactoring Workflow

### Phase 0: Zero-Risk Preparatory Changes

Start with changes that have no functional impact:

1. **Add missing `__init__.py`** files to packages using implicit namespace packages
2. **Fix incorrect import paths** (e.g., `from src.mt_server.config` → `from mt_server.config`)
3. **Fix logging bugs** (e.g., logging values before they're computed)
4. **Remove debug-only methods** that aren't used in production
5. **Run tests after each change** to verify no regressions

```bash
cd /opt/mt/nllb-server && uv run pytest tests/markdown2/ -v --tb=short
uv run ruff check src/mt_server/markdown2/
```

### Phase 0b: Orchestrator Cleanup

After Phase 0, clean up the orchestrator so its `process()` method reads as a declarative list of steps:

1. **Extract loop logic into a private method** — if one step is a loop (e.g., `_translate_chunks()`) while all others are single calls, extract it for symmetry
2. **Remove module-level globals** — move values like `settings.max_input_tokens` into constructor parameters (`max_tokens: Optional[int] = None`)
3. **Rename files to shorter names** — `markdown_translator.py` → `translator.py` (update all imports: source, tests, handlers)
4. **Replace `patch()` in tests with direct parameters** — when removing module-level globals, tests that patched them should pass values directly instead

**Why:** A module-level variable like `max_input_tokens = settings.max_input_tokens` is read once at import time, making the module fragile. A constructor parameter is explicit, testable, and doesn't require `patch()` in tests.

### Evaluating External Recommendations

When given expert recommendations (e.g., from `plans/refactoring_md2.html`):

1. **Verify each recommendation against current code state** — some may be stale (e.g., "delete reconstructor.py" when it's already gone)
2. **Assess risk level**: zero-risk, low-risk, medium-risk, high-risk
3. **Check for over-engineering** — recommendations to split a 188-line file into 3 classes may be excessive
4. **Prioritize by dependency** — some phases depend on others being completed first

### Common Module Issues to Look For

Based on actual analysis of `markdown2/`:

| Issue | Example | Fix Priority |
|-------|---------|--------------|
| Missing `__init__.py` | Implicit namespace package | High (causes import issues) |
| Circular dependencies | Handlers calling walker's private methods | High (blocks refactoring) |
| God Objects | `reconstructor/main.py` (357 lines) | Medium (readability) |
| Duplicate code | Close-marker creation in 4+ places | Medium (maintenance) |
| Wrong import paths | `from src.mt_server.config` | High (fragile) |
| Module-level globals | `max_input_tokens = settings.max_input_tokens` | Medium (fragile, hard to test) |
| Logging before computation | `len(self.translated_text)` before `reconstruct()` | Low (correctness) |
| Debug methods in production | `_blocks_qty()` only used in debug mode | Low (cleanup) |

### Pipeline Step Delegation Analysis

When analyzing an orchestrator's `process()` method, build a table mapping each step to where it's implemented:

| Step | What it does | Where implemented | Delegated? |
|------|-------------|-------------------|------------|
| 1 | Parse MD → AST | `parser.py` | ✅ |
| 2 | AST → TranslationUnit[] | `ast_walker/` | ✅ |
| 3 | Chunk | `chunker.py` | ✅ |
| 4 | Translate chunks | inline in `process()` | ❌ |
| 5 | Merge | `chunker.py` | ✅ |
| 6 | Reconstruct | `reconstructor/` | ✅ |

**Rule:** If all steps except one are single delegated calls, extract the outlier into a private method. Don't create a submodule for <50 lines of logic.

### Structural Reorganization (Phase 0c) — Execution Pattern

Group files by pipeline stage. A file belongs to a submodule if it's used by **only one** pipeline stage. Files shared by two or more stages go to `models/`.

**Structure after Phase 0c (executed):**
```
markdown2/
├── __init__.py            # public API
├── translator.py          # orchestrator (top level)
├── parser.py              # 32 lines, self-sufficient (top level)
├── chunker.py             # single file, too small for submodule (top level)
├── ast_walker/            # stage 2: AST traversal
│   ├── __init__.py        # exports ASTWalker
│   ├── walker.py          # (was ast_walker.py)
│   └── handlers/          # (was top-level handlers/)
│       ├── __init__.py
│       ├── context_block_handler.py
│       ├── structural_block_handler.py
│       ├── special_case_handler.py
│       └── inline_collector.py
├── reconstructor/         # stage 6: MD assembly
│   └── ... (7 files)
└── models/                # shared data models (used by ≥2 stages)
    ├── __init__.py        # re-exports all models
    ├── translation_unit.py
    ├── translation_unit_type.py
    ├── node_type.py
    ├── unit_factory.py
    └── placeholder.py
```

**Don't over-organize:** A single file (~263 lines) with a potential companion (~50 lines) doesn't need its own submodule — two files are easy to navigate without a directory.

### Mass File Move Procedure

When moving many files into submodules at once:

1. **Build a comprehensive import map first** — use an Explore agent to catalog ALL imports (internal between files, and external from tests + other modules). This prevents missing references.

2. **Move files with `git mv`** to preserve history. Can move entire directories at once:
   ```bash
   git mv src/.../ast_walker.py src/.../ast_walker/walker.py
   git mv src/.../handlers src/.../ast_walker/handlers  # directory move
   git mv src/.../translation_unit.py src/.../models/translation_unit.py
   ```

3. **Create `__init__.py` for each new submodule** with appropriate exports.

4. **Update imports level-by-level, innermost first:**
   - Innermost files first (handlers inside `ast_walker/handlers/`)
   - Then their parent (`ast_walker/walker.py`)
   - Then sibling submodules (`reconstructor/*.py`)
   - Then top-level files (`translator.py`, `chunker.py`)
   - Finally external consumers (tests, `handlers.py`)

5. **Relative import depth changes** — when a file moves deeper, its relative imports to siblings need an extra dot:
   ```python
   # handlers/ (was at markdown2/handlers/, now at markdown2/ast_walker/handlers/)
   # Old: from ..translation_unit import TranslationUnit      (1 level up)
   # New: from ...models.translation_unit import TranslationUnit (2 levels up)
   ```

6. **Use `replace_all` for batch updates** in large test files where the same import string appears many times (e.g., inline imports inside test methods).

7. **Run tests + linter after ALL moves are complete** — not after each individual file move, since imports are broken during the transition.

8. **Grep for stale references** after completion:
   ```
   grep_search for: from src.mt_server.markdown2.(translation_unit|placeholder|node_type|...)
   ```
   This catches any remaining old import paths in tests.

### Phase 0d: Placeholder System Refactoring (Critical for Production)

**Problem:** The original placeholder format `{lnk_1}` was being tokenized by NLLB as a translatable word, breaking the translation pipeline.

**Solution:** Changed to dunder format `__L_O_1__` (double underscores + single-letter codes + Open/Close markers).

**Implementation:**

1. **Created `models/placeholder_codes.py`** with centralized code mappings:
   - `PAIRED_CODES`: strong→B, em→I, link→L, s→D (with _O/_C suffixes)
   - `SINGLE_TRANSLATE_CODES`: image→G
   - `PROTECT_CODES`: code_inline→C, math_inline→M, html_inline→X, tasklist_item→T, softbreak→S, hardbreak→H, footnote_ref→F
   - `SEGMENT_SEPARATOR = " __S__ "` — centralized separator for chunker (replaces hardcoded `REC_SEPARATOR`)

2. **Updated `Placeholder` dataclass** with space context fields:
   ```python
   has_leading_space: bool = True
   has_trailing_space: bool = True
   ```

3. **Rewrote `PlaceholderManager.create_placeholder()`** to use dunder format and accept space context parameters.

4. **Updated `PlaceholderRestorer`** with simplified normalization:
   - New regex patterns for `__X_Y_N__` format
   - Single regex `_PLACEHOLDER_PUNCTUATION_RE` strips spaces between closing/atomic placeholders and punctuation (`__L_C_1__ .` → `__L_C_1__.`)
   - Collapses multiple spaces with `re.sub(r"  +", " ", ...)`

5. **Added space-guaranteeing in `InlineCollector._append_tag()`**:
   - Every placeholder tag is wrapped with spaces when appended to `extracted_text`
   - This ensures NLLB sees each placeholder as a separate token
   - Format: `Text __B_O_1__ word __B_C_1__ more text.` (all placeholders space-separated)

**Why this format works:**
- Double underscores are not natural word boundaries for NLLB tokenization
- Single-letter codes minimize token count
- Explicit O/C markers make pairing unambiguous
- Format is visually distinct from markdown syntax
- **Spaces around placeholders** prevent NLLB from merging them with adjacent words (critical lesson from post-0d fix)

**Critical post-0d lesson — placeholder spacing:**
After Phase 0d, placeholders still stuck to text (e.g., `__B_O_1__Международный банк__B_C_1__`), causing NLLB to corrupt them. The fix:
- `InlineCollector._append_tag()` always adds `" "` before and after each tag
- `PlaceholderRestorer.normalize_text()` uses a single regex to remove unwanted spaces before punctuation
- `chunker.py` imports `SEGMENT_SEPARATOR` from `placeholder_codes.py` instead of hardcoding

**Test updates required:**
- All test files with hardcoded `{lnk_1}` strings → `__L_O_1__`
- All `translation_dict` entries must include spaces around placeholders: `"Text __B_O_1__ bold __B_C_1__ ."` not `"Text __B_O_1__bold__B_C_1__."`
- `conftest.py` `integration_translation_dict` — both keys and values must have spaces around placeholders
- Mock placeholders in reconstructor tests — `extracted_text` and `translated_text` must have spaces
- Add `TestPlaceholderSpacing` regression tests to verify no placeholder sticks to adjacent text

### Phased Execution Strategy

| Phase | Focus | Risk | Dependencies | Status |
|-------|-------|------|--------------|--------|
| 0 | Preparatory fixes | Zero | None | ✅ Done |
| 0b | Orchestrator cleanup | Zero | None | ✅ Done |
| 0c | Structural reorganization | Low | Phase 0b | ✅ Done |
| 0d | Placeholder system | Medium | Phase 0c | ✅ Done |
| 1 | Break circular dependencies | Medium | Phase 0c | Next |
| 2 | Consolidate duplication | Medium | Phase 1 | Pending |
| 3 | Simplify complex mappings | Low | Phase 0c | Pending |
| 4 | Merge small modules | Low | Phase 1 | Pending |
| 5 | Refactor God Objects | Medium | Phase 2 | Pending |
| 6 | Improve data models | Low | Phase 4 | Pending |
| 7 | Optimize performance | Low | Phase 4 | Pending |

### Validation Checklist After Each Phase

- [ ] All `tests/markdown2/` tests pass without modifying test scenarios
- [ ] `ruff check` passes with no warnings on changed files
- [ ] Run `tests/service/` too if imports were renamed
- [ ] No new circular imports introduced
- [ ] No files exceed 250 lines (target)
- [ ] All imports use canonical paths (`from mt_server...`, not `from src.mt_server...`)
- [ ] Each package has `__init__.py`

## Key Files Reference (current state after Phase 0d)

### Entry Points
- `markdown2/__init__.py` — public API (`MarkdownTranslator`)
- `markdown2/translator.py` — orchestrator (pipeline coordinator, ~140 lines)

### Core Components
- `markdown2/ast_walker/walker.py` — DFS traversal, delegates to handlers
- `markdown2/ast_walker/handlers/` — 4 handlers (context_block, structural_block, special_case, inline_collector)
- `markdown2/chunker.py` — text chunking for NLLB token limits
- `markdown2/reconstructor/main.py` — rebuilds Markdown from translated units
- `markdown2/models/` — shared data models (translation_unit, node_type, placeholder, unit_factory, translation_unit_type, **placeholder_codes**)

### Placeholder System (Phase 0d)
- `markdown2/models/placeholder_codes.py` — centralized mapping of node types to single-letter codes (B, I, L, C, M, etc.)
- `markdown2/models/placeholder.py` — `Placeholder` dataclass with `has_leading_space`/`has_trailing_space` fields
- `markdown2/reconstructor/placeholder_restorer.py` — restores `__X_Y_N__` format back to markdown

### Problem Areas
- `ast_walker/handlers/` — circular dependencies with walker (handlers call walker's private methods)
- `reconstructor/main.py` — God Object (357 lines), dual table processing paths
- `models/node_type.py` — complex dynamic mapping construction

## When to Reject Recommendations

Reject or modify recommendations that:
- **Are stale**: reference files/code that no longer exists
- **Are over-engineering**: propose 3 classes for what 1 class handles fine; propose a submodule for a single file
- **Risk data loss**: suggest deleting fallback code that handles real edge cases
- **Add complexity without benefit**: wrapper classes for simple functions

## Import Migration Pattern (Phase 0b lesson)

When renaming a file like `markdown_translator.py` → `translator.py`:

1. `git mv` the file (preserves history)
2. `grep_search` for the old name across the entire project
3. Update imports in: `__init__.py`, `handlers.py` (lazy imports), test files (both import paths and `patch()` targets)
4. If tests used `patch("module.old_name.variable")` — replace with direct constructor parameters when possible
5. Remove now-unused imports (e.g., `patch` from `unittest.mock`)
6. Run both unit tests and integration tests that reference the module

## Related Skills

- `debugging-markdown-translation-tests` — for understanding test failures during refactoring
