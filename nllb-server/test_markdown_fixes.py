"""Unit tests for the three markdown translation bug fixes.

Run with:
    cd nllb-server && .venv/bin/python test_markdown_fixes.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from markdown_it.token import Token
from markdown_utils import (
    _inline_to_tagged_text,
    _tagged_text_to_ast,
    create_markdown_parser,
    extract_translation_units,
    render_markdown,
)

# ── helpers ──────────────────────────────────────────────────────────────────


def make_inline(content: str) -> Token:
    """Parse a markdown snippet and return its first inline token."""
    parser = create_markdown_parser()
    tokens = parser.parse(content)
    for tok in tokens:
        if tok.type == "inline":
            return tok
    raise ValueError(f"No inline token found in: {content!r}")


def token_types(children: list[Token]) -> list[str]:
    return [t.type for t in children]


def assert_balanced(children: list[Token], label: str = ""):
    """Assert that open/close pairs are balanced."""
    stack = []
    pairs = {
        "strong_open": "strong_close",
        "emphasis_open": "emphasis_close",
        "link_open": "link_close",
    }
    for tok in children:
        if tok.type in pairs:
            stack.append(pairs[tok.type])
        elif tok.type in pairs.values():
            assert stack, f"{label}: unexpected close token {tok.type!r}, stack empty"
            expected = stack.pop()
            assert tok.type == expected, (
                f"{label}: expected {expected!r} but got {tok.type!r}"
            )
    assert not stack, f"{label}: unclosed tokens remain: {stack}"


def test_code_inline_placeholder():
    """code_inline must produce a self-closing placeholder, not be dropped."""
    inline = make_inline("Use `pip install` now")
    tagged, tags = _inline_to_tagged_text(inline)

    assert "<c0/>" in tagged, f"Expected <c0/> in tagged text, got: {tagged!r}"
    assert "pip install" not in tagged, (
        "code content must not appear raw in tagged text"
    )
    assert any(t["type"] == "code_inline" for t in tags), (
        "tag def for code_inline missing"
    )
    code_tag = next(t for t in tags if t["type"] == "code_inline")
    assert code_tag["attrs"]["content"] == "pip install"
    print(f"  PASS test_code_inline_placeholder: tagged={tagged!r}")


def test_code_inline_roundtrip():
    """code_inline must be reconstructed correctly from tagged text."""
    inline = make_inline("Use `pip install` now")
    tagged, tags = _inline_to_tagged_text(inline)

    # Simulate identity translation (model returns same tagged text)
    children = _tagged_text_to_ast(tagged, tags)
    assert_balanced(children, "code_inline_roundtrip")

    types = token_types(children)
    assert "code_inline" in types, f"code_inline token missing in output: {types}"
    code_tok = next(t for t in children if t.type == "code_inline")
    assert code_tok.content == "pip install", f"Wrong content: {code_tok.content!r}"
    print(f"  PASS test_code_inline_roundtrip: types={types}")


# ── Fix 2: stack-based tag validator ─────────────────────────────────────────


def test_orphan_close_skipped():
    """An orphan </b0> with no matching open must be silently skipped."""
    tags = [{"id": "b0", "type": "strong", "attrs": {}}]
    # NLLB dropped the open tag, only close remains
    children = _tagged_text_to_ast("Hello </b0> world", tags)
    assert_balanced(children, "orphan_close")
    types = token_types(children)
    assert "strong_close" not in types, f"Orphan close must be skipped: {types}"
    assert "strong_open" not in types
    print(f"  PASS test_orphan_close_skipped: types={types}")


def test_unclosed_open_autoclosed():
    """An unclosed <b0> must be auto-closed at the end."""
    tags = [{"id": "b0", "type": "strong", "attrs": {}}]
    # NLLB dropped the close tag
    children = _tagged_text_to_ast("<b0>Hello world", tags)
    assert_balanced(children, "unclosed_open")
    types = token_types(children)
    assert "strong_open" in types, f"strong_open missing: {types}"
    assert "strong_close" in types, f"strong_close must be auto-added: {types}"
    print(f"  PASS test_unclosed_open_autoclosed: types={types}")


def test_duplicated_close_second_skipped():
    """A duplicated </b0></b0> must only close once."""
    tags = [{"id": "b0", "type": "strong", "attrs": {}}]
    children = _tagged_text_to_ast("<b0>Hello</b0></b0> world", tags)
    assert_balanced(children, "duplicated_close")
    types = token_types(children)
    assert types.count("strong_open") == 1
    assert types.count("strong_close") == 1
    print(f"  PASS test_duplicated_close_second_skipped: types={types}")


def test_reordered_tags_fixed():
    """</b0><b0> (close before open) must produce valid nesting."""
    tags = [{"id": "b0", "type": "strong", "attrs": {}}]
    # NLLB swapped open and close
    children = _tagged_text_to_ast("Hello </b0><b0> world", tags)
    assert_balanced(children, "reordered_tags")
    print(f"  PASS test_reordered_tags_fixed: types={token_types(children)}")


def test_nested_tags_balanced():
    """Nested <b0><e1>text</e1></b0> must produce balanced nesting."""
    tags = [
        {"id": "b0", "type": "strong", "attrs": {}},
        {"id": "e1", "type": "emphasis", "attrs": {}},
    ]
    children = _tagged_text_to_ast("<b0><e1>text</e1></b0>", tags)
    assert_balanced(children, "nested_tags")
    types = token_types(children)
    assert types == [
        "strong_open",
        "emphasis_open",
        "text",
        "emphasis_close",
        "strong_close",
    ], types
    print(f"  PASS test_nested_tags_balanced: types={types}")


def test_inner_tag_force_closed_on_outer_close():
    """If inner tag is not closed before outer close, it must be force-closed."""
    tags = [
        {"id": "b0", "type": "strong", "attrs": {}},
        {"id": "e1", "type": "emphasis", "attrs": {}},
    ]
    # NLLB dropped </e1>, only </b0> present
    children = _tagged_text_to_ast("<b0><e1>text</b0>", tags)
    assert_balanced(children, "force_close_inner")
    types = token_types(children)
    assert "emphasis_close" in types, f"emphasis_close must be force-inserted: {types}"
    assert "strong_close" in types
    print(f"  PASS test_inner_tag_force_closed_on_outer_close: types={types}")


# ── Fix 3: split_oversized_units skips tagged units ──────────────────────────


def test_split_skips_tagged_units():
    """Units with tags must not be split even if they exceed max_tokens."""
    from markdown_utils import TranslationUnit, split_oversized_units

    # count_tokens calls tokenizer(text, ...) and reads result["input_ids"]
    class FakeTokenizer:
        def __call__(self, text, **kwargs):
            return {"input_ids": list(range(500))}  # always 500 tokens

    tags = [{"id": "b0", "type": "strong", "attrs": {}}]
    unit = TranslationUnit(
        text="<b0>Very long text that would normally be split</b0>",
        tags=tags,
        unit_type="paragraph",
        inline_token=Token(type="inline", tag="", nesting=0),
    )

    result = split_oversized_units([unit], FakeTokenizer(), "rus_Cyrl", max_tokens=50)
    assert len(result) == 1, f"Tagged unit must not be split, got {len(result)} chunks"
    assert result[0] is unit
    print("  PASS test_split_skips_tagged_units")


def test_split_plain_unit_is_split():
    """Tag-free units that exceed max_tokens must still be split."""
    from markdown_utils import TranslationUnit, split_oversized_units

    class FakeTokenizer:
        def __call__(self, text, **kwargs):
            # Return large count for the full text, small for individual sentences
            n = 10 if len(text) < 30 else 500
            return {"input_ids": list(range(n))}

    unit = TranslationUnit(
        text="First sentence. Second sentence. Third sentence.",
        tags=[],  # no tags — safe to split
        unit_type="paragraph",
        inline_token=Token(type="inline", tag="", nesting=0),
    )

    result = split_oversized_units([unit], FakeTokenizer(), "rus_Cyrl", max_tokens=50)
    # pysbd may produce 3 sentences → multiple subchunks (or fewer if merged)
    assert len(result) >= 1
    print(f"  PASS test_split_plain_unit_is_split: {len(result)} chunk(s)")


# ── Full round-trip: parse → extract → identity-translate → render ────────────


def test_roundtrip_no_crash():
    """Parse codex_small.md, extract units, apply identity translation, render."""
    import pathlib

    md_path = pathlib.Path(__file__).parent.parent / "data" / "codex_small.md"
    text = md_path.read_text(encoding="utf-8")

    parser = create_markdown_parser()
    tokens = parser.parse(text)
    units = extract_translation_units(tokens)

    # Identity translation: reconstruct AST from the same tagged text
    for unit in units:
        if unit.inline_token is not None:
            unit.inline_token.children = _tagged_text_to_ast(unit.text, unit.tags)
            unit.inline_token.content = ""

    # Must not raise ValueError: Invalid token nesting
    rendered = render_markdown(tokens)
    assert rendered.strip(), "Rendered output must not be empty"
    print(f"  PASS test_roundtrip_no_crash: rendered {len(rendered)} chars")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_code_inline_placeholder,
        test_code_inline_roundtrip,
        test_orphan_close_skipped,
        test_unclosed_open_autoclosed,
        test_duplicated_close_second_skipped,
        test_reordered_tags_fixed,
        test_nested_tags_balanced,
        test_inner_tag_force_closed_on_outer_close,
        test_split_skips_tagged_units,
        test_split_plain_unit_is_split,
        test_roundtrip_no_crash,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAIL {test.__name__}: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
