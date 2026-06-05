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

### Structural Reorganization Principle (Phase 0c)

Group files by pipeline stage. A file belongs to a submodule if it's used by **only one** pipeline stage. Files shared by two or more stages go to `models/`.

**Target structure:**
```
markdown2/
├── __init__.py            # public API
├── translator.py          # orchestrator (top level)
├── parser.py              # 32 lines, self-sufficient (top level)
├── chunker.py             # single file, too small for submodule (top level)
├── ast_walker/            # stage 2: AST traversal
│   ├── walker.py
│   └── handlers/          # only used by walker
├── reconstructor/         # stage 6: MD assembly (already a submodule)
└── models/                # shared data models (used by ≥2 stages)
    ├── translation_unit.py
    ├── node_type.py
    └── placeholder.py
```

**Don't over-organize:** A single file (~263 lines) with a potential companion (~50 lines) doesn't need its own submodule — two files are easy to navigate without a directory.

### Phased Execution Strategy

| Phase | Focus | Risk | Dependencies |
|-------|-------|------|--------------|
| 0 | Preparatory fixes | Zero | None |
| 0b | Orchestrator cleanup | Zero | None |
| 0c | Structural reorganization | Low | Phase 0b |
| 1 | Break circular dependencies | Medium | Phase 0c |
| 2 | Consolidate duplication | Medium | Phase 1 |
| 3 | Simplify complex mappings | Low | Phase 0c |
| 4 | Merge small modules | Low | Phase 1 |
| 5 | Refactor God Objects | Medium | Phase 2 |
| 6 | Improve data models | Low | Phase 4 |
| 7 | Optimize performance | Low | Phase 4 |

### Validation Checklist After Each Phase

- [ ] All `tests/markdown2/` tests pass without modifying test scenarios
- [ ] `ruff check` passes with no warnings on changed files
- [ ] Run `tests/service/` too if imports were renamed
- [ ] No new circular imports introduced
- [ ] No files exceed 250 lines (target)
- [ ] All imports use canonical paths (`from mt_server...`, not `from src.mt_server...`)
- [ ] Each package has `__init__.py`

## Key Files Reference

### Entry Points
- `markdown2/__init__.py` — public API (`MarkdownTranslator`)
- `markdown2/translator.py` — orchestrator (pipeline coordinator, ~100 lines after Phase 0b)

### Core Components
- `ast_walker/` (future: submodule) — DFS traversal, delegates to handlers
- `chunker.py` — text chunking for NLLB token limits
- `reconstructor/main.py` — rebuilds Markdown from translated units
- `models/` (future: submodule) — shared data models

### Problem Areas (as of Phase 0b)
- `handlers/` — circular dependencies with `ast_walker.py`
- `reconstructor/main.py` — God Object (357 lines), dual table processing paths
- `node_type.py` — complex dynamic mapping construction
- `placeholder.py` — 3 responsibilities in one class

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
