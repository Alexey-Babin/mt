"""Markdown-aware translation with placeholder-based formatting preservation.

This module preserves markdown formatting using the industry-standard placeholder approach:
1. Parse markdown to AST
2. Convert inline formatting to tagged placeholders (e.g., Hello <b0>beautiful</b0>)
3. Extract tagged text as translation unit
4. Translate
5. Parse tagged translated text and reconstruct AST

Translation units: heading, paragraph, list_item, blockquote, table_cell, image_alt
Skipped: code blocks (fence, code_block), inline code (code_inline), URLs
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from config import config
from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from utils import count_tokens, get_segmenter

# ── Markdown Parser ──────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def create_markdown_parser() -> MarkdownIt:
    """Create configured markdown parser with feature support."""
    return (
        MarkdownIt("commonmark")
        .use(front_matter_plugin)
        .use(tasklists_plugin)
        .enable("table")
    )


# ── Markdown Detection ───────────────────────────────────────────────────────

_MARKDOWN_PATTERNS = [
    r"^#{1,6}\s",  # Headings
    r"^[-*+]\s",  # List items
    r"^\d+\.\s",  # Ordered lists
    r"^>\s",  # Blockquotes
    r"```",  # Code blocks
    r"\|.*\|",  # Tables
    r"\*\*.*\*\*",  # Bold
    r"\*[^*].*\*",  # Italic (single asterisk)
    r"_[^_].*_\b",  # Italic (underscore)
    r"\[.*\]\(.*\)",  # Links
    r"!\[.*\]\(.*\)",  # Images
    r"^---+$",  # Horizontal rules
    r"^\*\*\*+$",  # Horizontal rules
    r"^_{3,}$",  # Horizontal rules
]


def detect_markdown(text: str) -> bool:
    """Heuristic detection of markdown content."""
    return any(re.search(p, text, re.MULTILINE) for p in _MARKDOWN_PATTERNS)


# ── Translation Unit ─────────────────────────────────────────────────────────


@dataclass
class TranslationUnit:
    """A block-level element ready for translation."""

    text: str  # Tagged text content (e.g., "Hello <b0>beautiful</b0>")
    tags: list[
        dict
    ]  # List of tag definitions: {"id": "b0", "type": "strong", "attrs": {}}
    unit_type: str  # 'heading', 'paragraph', 'list_item', 'blockquote', 'table_cell', 'image_alt'
    inline_token: Token | None = None  # Reference to the inline token to update
    needs_split: bool = False  # True if oversized (split into subchunks)
    parent_unit: TranslationUnit | None = None  # For subchunks, reference to original


# ── Tag-based Text Extraction ────────────────────────────────────────────────

# Tag pattern for matching placeholders in translated text.
# Matches: <b0>  </b0>  <c0/>  (self-closing for code_inline)
_TAG_PATTERN = re.compile(r"<(/?)(\w+)(\d+)(/?)>")


def _inline_to_tagged_text(inline: Token) -> tuple[str, list[dict]]:
    """Convert inline token to tagged text and tag definitions.

    Example:
        Input AST: Hello **beautiful** [world](x)
        Output: ("Hello <b0>beautiful</b0> <a1>world</a1>", [
            {"id": "b0", "type": "strong", "attrs": {}},
            {"id": "a1", "type": "link", "attrs": {"href": "x"}}
        ])
    """
    tags: list[dict] = []
    tag_counter = 0

    def _process_children(children: list[Token] | None) -> str:
        nonlocal tag_counter
        result = []
        for child in children or []:
            if child.type == "text":
                result.append(child.content)
            elif child.type in ("softbreak", "hardbreak"):
                result.append(" ")
            elif child.type == "strong_open":
                tag_id = f"b{tag_counter}"
                tag_counter += 1
                tags.append({"id": tag_id, "type": "strong", "attrs": {}})
                result.append(f"<{tag_id}>")
            elif child.type == "strong_close":
                # Find matching open tag
                for tag in reversed(tags):
                    if tag["type"] == "strong" and not tag.get("closed"):
                        tag["closed"] = True
                        result.append(f"</{tag['id']}>")
                        break
            elif child.type == "emphasis_open":
                tag_id = f"e{tag_counter}"
                tag_counter += 1
                tags.append({"id": tag_id, "type": "emphasis", "attrs": {}})
                result.append(f"<{tag_id}>")
            elif child.type == "emphasis_close":
                for tag in reversed(tags):
                    if tag["type"] == "emphasis" and not tag.get("closed"):
                        tag["closed"] = True
                        result.append(f"</{tag['id']}>")
                        break
            elif child.type == "link_open":
                tag_id = f"a{tag_counter}"
                tag_counter += 1
                attrs = dict(child.attrs) if child.attrs else {}
                tags.append({"id": tag_id, "type": "link", "attrs": attrs})
                result.append(f"<{tag_id}>")
            elif child.type == "link_close":
                for tag in reversed(tags):
                    if tag["type"] == "link" and not tag.get("closed"):
                        tag["closed"] = True
                        result.append(f"</{tag['id']}>")
                        break
            elif child.type == "code_inline":
                # Preserve inline code as a self-closing placeholder.
                # Content is stored in the tag definition and reconstructed later.
                tag_id = f"c{tag_counter}"
                tag_counter += 1
                tags.append(
                    {
                        "id": tag_id,
                        "type": "code_inline",
                        "attrs": {"content": child.content},
                    }
                )
                result.append(f"<{tag_id}/>")
            elif child.type == "image":
                # Extract alt text from image children
                alt_text = "".join(
                    c.content for c in (child.children or []) if c.type == "text"
                )
                if alt_text:
                    result.append(alt_text)
            else:
                # Recurse into children for other types
                if child.children:
                    result.append(_process_children(child.children))
        return "".join(result)

    tagged_text = _process_children(inline.children)
    return tagged_text, tags


def _tagged_text_to_ast(tagged_text: str, tags: list[dict]) -> list[Token]:
    """Convert tagged text back to AST children tokens.

    Uses a stack-based validator to guarantee balanced open/close pairs even
    when NLLB drops, duplicates, or reorders placeholder tags:
      - Orphan close tags (no matching open on stack) are silently skipped.
      - Unclosed open tags still on the stack are auto-closed at the end.
      - Self-closing tags (<c0/>) are emitted as code_inline tokens directly.

    Example:
        Input: "Hola <b0>hermoso</b0> <a1>mundo</a1>"
        Output: [text("Hola "), strong_open, text("hermoso"), strong_close,
                 text(" "), link_open(href="x"), text("mundo"), link_close]
    """
    children: list[Token] = []

    def _make_token(type: str, tag: str = "", nesting: int = 0) -> Token:
        t = Token(type=type, tag=tag, nesting=nesting)  # type: ignore
        t.content = ""
        t.level = 0
        return t

    # Build a lookup from tag_id → tag_def for O(1) access
    tag_lookup: dict[str, dict] = {tag["id"]: tag for tag in tags}

    # Stack of currently open tag_ids (most recent last)
    open_stack: list[str] = []

    last_end = 0
    for match in _TAG_PATTERN.finditer(tagged_text):
        is_close = match.group(1) == "/"
        tag_type_str = match.group(2)  # b, e, a, c
        tag_num = match.group(3)  # 0, 1, 2 …
        is_self_closing = match.group(4) == "/"
        tag_id = f"{tag_type_str}{tag_num}"
        start, end = match.span()

        # Emit any plain text before this tag
        if start > last_end:
            text_content = tagged_text[last_end:start]
            if text_content:
                t = _make_token("text")
                t.content = text_content
                children.append(t)

        tag_def = tag_lookup.get(tag_id)

        if tag_def is None:
            # Unknown tag id (hallucinated by model) — skip
            last_end = end
            continue

        tag_type = tag_def["type"]

        if is_self_closing:
            # Self-closing placeholder: reconstruct code_inline token
            if tag_type == "code_inline":
                t = _make_token("code_inline", "code", 0)
                t.content = tag_def["attrs"].get("content", "")
                t.markup = "`"
                children.append(t)
            # (other self-closing types can be added here)

        elif is_close:
            # Closing tag — only emit if this tag_id is currently open on the stack.
            # If it is not on the stack, NLLB hallucinated an orphan close → skip.
            if tag_id in open_stack:
                # Pop everything above it first (force-close inner tags to keep nesting valid)
                while open_stack and open_stack[-1] != tag_id:
                    inner_id = open_stack.pop()
                    inner_def = tag_lookup.get(inner_id)
                    if inner_def:
                        children.extend(_close_tokens_for(inner_def, _make_token))
                # Now pop and close the matched tag
                if open_stack:
                    open_stack.pop()
                children.extend(_close_tokens_for(tag_def, _make_token))
            # else: orphan close — silently skip

        else:
            # Opening tag
            open_stack.append(tag_id)
            children.extend(_open_tokens_for(tag_def, _make_token))

        last_end = end

    # Emit any trailing plain text
    if last_end < len(tagged_text):
        text_content = tagged_text[last_end:]
        if text_content:
            t = _make_token("text")
            t.content = text_content
            children.append(t)

    # Auto-close any tags still open on the stack (NLLB dropped their close tags)
    while open_stack:
        unclosed_id = open_stack.pop()
        unclosed_def = tag_lookup.get(unclosed_id)
        if unclosed_def:
            children.extend(_close_tokens_for(unclosed_def, _make_token))

    return children


def _open_tokens_for(tag_def: dict, make: Any) -> list[Token]:
    """Return the opening token(s) for a tag definition."""
    tag_type = tag_def["type"]
    if tag_type == "strong":
        return [make("strong_open", "strong", 1)]
    elif tag_type == "emphasis":
        return [make("emphasis_open", "em", 1)]
    elif tag_type == "link":
        t = make("link_open", "a", 1)
        if tag_def.get("attrs"):
            # markdown-it-py Token.attrs must be a dict
            t.attrs = dict(tag_def["attrs"])
        return [t]
    return []


def _close_tokens_for(tag_def: dict, make: Any) -> list[Token]:
    """Return the closing token(s) for a tag definition."""
    tag_type = tag_def["type"]
    if tag_type == "strong":
        return [make("strong_close", "strong", -1)]
    elif tag_type == "emphasis":
        return [make("emphasis_close", "em", -1)]
    elif tag_type == "link":
        return [make("link_close", "a", -1)]
    return []


# ── Extract Translation Units ────────────────────────────────────────────────


def _extract_images_from_inline(inline: Token) -> list[TranslationUnit]:
    """Extract image alt text units from inline token children."""
    units = []
    for child in inline.children or []:
        if child.type == "image":
            alt_text = "".join(
                c.content for c in (child.children or []) if c.type == "text"
            )
            if alt_text.strip():
                units.append(
                    TranslationUnit(text=alt_text, tags=[], unit_type="image_alt")
                )
    return units


def extract_translation_units(tokens: list[Token]) -> list[TranslationUnit]:
    """
    Walk AST, extract block-level translation units with tagged text.

    Skips: code blocks (fence, code_block), inline code (code_inline), URLs.
    """
    units: list[TranslationUnit] = []

    for i, token in enumerate(tokens):
        # Skip code blocks entirely
        if token.type in ("fence", "code_block"):
            continue

        # Heading
        if token.type == "heading_open":
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            if inline and inline.type == "inline":
                tagged_text, tags = _inline_to_tagged_text(inline)
                if tagged_text.strip():
                    units.append(
                        TranslationUnit(
                            text=tagged_text,
                            tags=tags,
                            unit_type="heading",
                            inline_token=inline,
                        )
                    )
                units.extend(_extract_images_from_inline(inline))
            continue

        # Paragraph
        if token.type == "paragraph_open":
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            if inline and inline.type == "inline":
                tagged_text, tags = _inline_to_tagged_text(inline)
                if tagged_text.strip():
                    units.append(
                        TranslationUnit(
                            text=tagged_text,
                            tags=tags,
                            unit_type="paragraph",
                            inline_token=inline,
                        )
                    )
                units.extend(_extract_images_from_inline(inline))
            continue

        # List item
        if token.type == "list_item_open":
            j = i + 1
            while j < len(tokens) and tokens[j].type != "list_item_close":
                if tokens[j].type == "paragraph_open" and j + 1 < len(tokens):
                    inline = tokens[j + 1]
                    if inline.type == "inline":
                        tagged_text, tags = _inline_to_tagged_text(inline)
                        if tagged_text.strip():
                            units.append(
                                TranslationUnit(
                                    text=tagged_text,
                                    tags=tags,
                                    unit_type="list_item",
                                    inline_token=inline,
                                )
                            )
                        units.extend(_extract_images_from_inline(inline))
                    break
                elif tokens[j].type == "inline":
                    tagged_text, tags = _inline_to_tagged_text(tokens[j])
                    if tagged_text.strip():
                        units.append(
                            TranslationUnit(
                                text=tagged_text,
                                tags=tags,
                                unit_type="list_item",
                                inline_token=tokens[j],
                            )
                        )
                    units.extend(_extract_images_from_inline(tokens[j]))
                    break
                j += 1
            continue

        # Blockquote
        if token.type == "blockquote_open":
            j = i + 1
            while j < len(tokens) and tokens[j].type != "blockquote_close":
                if tokens[j].type == "paragraph_open" and j + 1 < len(tokens):
                    inline = tokens[j + 1]
                    if inline.type == "inline":
                        tagged_text, tags = _inline_to_tagged_text(inline)
                        if tagged_text.strip():
                            units.append(
                                TranslationUnit(
                                    text=tagged_text,
                                    tags=tags,
                                    unit_type="blockquote",
                                    inline_token=inline,
                                )
                            )
                        units.extend(_extract_images_from_inline(inline))
                    break
                elif tokens[j].type == "inline":
                    tagged_text, tags = _inline_to_tagged_text(tokens[j])
                    if tagged_text.strip():
                        units.append(
                            TranslationUnit(
                                text=tagged_text,
                                tags=tags,
                                unit_type="blockquote",
                                inline_token=tokens[j],
                            )
                        )
                    units.extend(_extract_images_from_inline(tokens[j]))
                    break
                j += 1
            continue

        # Table header cell
        if token.type == "th_open":
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            if inline and inline.type == "inline":
                tagged_text, tags = _inline_to_tagged_text(inline)
                if tagged_text.strip():
                    units.append(
                        TranslationUnit(
                            text=tagged_text,
                            tags=tags,
                            unit_type="table_cell",
                            inline_token=inline,
                        )
                    )
                units.extend(_extract_images_from_inline(inline))
            continue

        # Table data cell
        if token.type == "td_open":
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            if inline and inline.type == "inline":
                tagged_text, tags = _inline_to_tagged_text(inline)
                if tagged_text.strip():
                    units.append(
                        TranslationUnit(
                            text=tagged_text,
                            tags=tags,
                            unit_type="table_cell",
                            inline_token=inline,
                        )
                    )
                units.extend(_extract_images_from_inline(inline))
            continue

    return units


# ── Split Oversized Units ────────────────────────────────────────────────────


def split_oversized_units(
    units: list[TranslationUnit], tokenizer: Any, nllb_lang_code: str, max_tokens: int
) -> list[TranslationUnit]:
    """
    Split units that exceed max_tokens into sentence-level subchunks.

    Each subchunk references the same tags as the parent unit.
    Individual sentences exceeding max_tokens are split by words.
    """
    from utils import split_long_sentence

    result: list[TranslationUnit] = []

    for unit in units:
        token_count = count_tokens(tokenizer, unit.text)

        if token_count <= max_tokens:
            result.append(unit)
        elif unit.tags:
            # Unit has inline formatting placeholders — never split it.
            # Splitting placeholderized text can break open/close tag pairs
            # across chunk boundaries, causing invalid token nesting after
            # translation.  Send the whole unit and let the model handle it.
            result.append(unit)
        else:
            # Tag-free unit: safe to split by sentences
            segmenter = get_segmenter(nllb_lang_code)
            segments = segmenter.segment(unit.text)
            sentences = [s.strip() for s in segments if s.strip()]

            current_chunk: list[str] = []
            current_tokens = 0

            for sentence in sentences:
                sent_tokens = count_tokens(tokenizer, sentence)

                # If a single sentence exceeds max_tokens, split it by words
                if sent_tokens > max_tokens:
                    if current_chunk:
                        result.append(
                            TranslationUnit(
                                text=" ".join(current_chunk),
                                tags=unit.tags,
                                unit_type=unit.unit_type,
                                inline_token=unit.inline_token,
                                needs_split=True,
                                parent_unit=unit,
                            )
                        )
                        current_chunk = []
                        current_tokens = 0

                        word_chunks = split_long_sentence(
                            tokenizer, sentence, max_tokens
                        )
                        for word_chunk in word_chunks:
                            result.append(
                                TranslationUnit(
                                    text=word_chunk,
                                    tags=unit.tags,
                                    unit_type=unit.unit_type,
                                    inline_token=unit.inline_token,
                                    needs_split=True,
                                    parent_unit=unit,
                                )
                            )
                    continue

                if current_tokens + sent_tokens > max_tokens and current_chunk:
                    result.append(
                        TranslationUnit(
                            text=" ".join(current_chunk),
                            tags=unit.tags,
                            unit_type=unit.unit_type,
                            inline_token=unit.inline_token,
                            needs_split=True,
                            parent_unit=unit,
                        )
                    )
                    current_chunk = []
                    current_tokens = 0

                current_chunk.append(sentence)
                current_tokens += sent_tokens

            if current_chunk:
                result.append(
                    TranslationUnit(
                        text=" ".join(current_chunk),
                        tags=unit.tags,
                        unit_type=unit.unit_type,
                        inline_token=unit.inline_token,
                        needs_split=True,
                        parent_unit=unit,
                    )
                )

    return result


# ── Map Translations Back ────────────────────────────────────────────────────


def map_translations_back(units: list[TranslationUnit], translated_texts: list[str]):
    """
    Replace inline token children with reconstructed AST from translated tagged text.

    For split units (subchunks), concatenate translations before reconstructing.
    """
    # Group subchunks by inline_token (use id as key)
    token_translations: dict[int, list[tuple[TranslationUnit, str]]] = {}

    for unit, translated in zip(units, translated_texts):
        if unit.inline_token is None:
            # Simple text unit (e.g., image alt) - no inline token to update
            continue
        key = id(unit.inline_token)
        if key not in token_translations:
            token_translations[key] = []
        token_translations[key].append((unit, translated))

    # For each group, reconstruct AST and update the original inline token
    for token_id, pairs in token_translations.items():
        if len(pairs) == 1:
            unit, translated = pairs[0]
            _update_inline_from_translated(unit, translated)
        else:
            concatenated = " ".join(t for _, t in pairs)
            unit = pairs[0][0]
            _update_inline_from_translated(unit, concatenated)


def _update_inline_from_translated(unit: TranslationUnit, translated_text: str):
    """Update the inline token's children from translated tagged text."""
    if unit.inline_token is None:
        return

    # Reconstruct AST children from translated tagged text
    new_children = _tagged_text_to_ast(translated_text, unit.tags)

    # Replace the inline token's children
    unit.inline_token.children = new_children
    unit.inline_token.content = ""


# ── Render Markdown ──────────────────────────────────────────────────────────


def render_markdown(tokens: list[Token]) -> str:
    """Render AST back to markdown string using mdformat renderer."""
    from mdformat.renderer import MDRenderer

    renderer = MDRenderer()
    return renderer.render(tokens, {}, {})


# ── Main Translation Flow ────────────────────────────────────────────────────


def translate_markdown(
    text: str,
    tokenizer: Any,
    model: Any,
    src_lang: str,
    tgt_lang: str,
    batch_size: int = 8,
) -> str:
    """
    Translate markdown text while preserving formatting.

    Flow:
    1. Parse markdown to AST
    2. Extract translation units with tagged text
    3. Split oversized units
    4. Batch translate
    5. Map translations back to AST (reconstruct from tagged text)
    6. Render markdown
    """
    parser = create_markdown_parser()
    tokens = parser.parse(text)

    # 1. Extract translation units
    units = extract_translation_units(tokens)

    if not units:
        return text  # Nothing to translate

    # 2. Split oversized units
    units = split_oversized_units(units, tokenizer, src_lang, config.max_input_tokens)

    # 3. Batch translate
    translated_texts = []
    for i in range(0, len(units), batch_size):
        batch = units[i : i + batch_size]
        batch_texts = [u.text for u in batch]
        try:
            # Tokenize batch (no truncation - chunks are already sized correctly)
            inputs = tokenizer(
                batch_texts,
                return_tensors="pt",
                truncation=False,
                max_length=config.tokenizer_max_length,
                padding=True,
            ).to(model.device)

            # Generate
            output_tokens = model.generate(
                **inputs,
                forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt_lang),
                max_new_tokens=config.max_new_tokens,
                use_cache=True,
            )

            # Decode
            batch_translated = tokenizer.batch_decode(
                output_tokens, skip_special_tokens=True
            )
            translated_texts.extend(batch_translated)
        except Exception:
            print(batch_texts)
            raise

    # 4. Map translations back to AST
    map_translations_back(units, translated_texts)

    # 5. Render markdown
    return render_markdown(tokens)
