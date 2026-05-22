from __future__ import annotations

import regex as re

MARKDOWN_PATTERNS = [
    re.compile(r"```"),
    re.compile(r"(?m)^#{1,6}\s"),
    re.compile(r"\[.+?\]\(.+?\)"),
    re.compile(r"\*\*.+?\*\*"),
    re.compile(r"(?<!`)`[^`\n]+`(?!`)"),
    re.compile(r"(?m)^\s*[-*+]\s"),
    re.compile(r"(?m)^\s*\d+\.\s"),
    re.compile(r"(?m)^>\s"),
    re.compile(r"(?m)^\|.+\|"),
]


def looks_like_markdown(text: str) -> bool:
    if not text.strip():
        return False

    for pattern in MARKDOWN_PATTERNS:
        if pattern.search(text):
            return True

    return False
