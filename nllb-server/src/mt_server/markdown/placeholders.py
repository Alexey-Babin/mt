from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from markdown_it.token import Token

logger = logging.getLogger("uvicorn.error")


class TranslateFunc(Protocol):
    def __call__(self, text: str) -> str: ...


@dataclass
class InlineSegment:
    """Один сегмент inline-содержимого."""

    text: str  # текст для перевода (может быть пустым для нетекстовых сегментов)
    translatable: bool  # нужно ли переводить
    prefix: str = ""  # markdown-разметка до текста (напр. "**")
    suffix: str = ""  # markdown-разметка после текста (напр. "**")


def _get_fmt_tags(token_type: str) -> tuple[str, str] | None:
    """Возвращает (open_tag, close_tag) для форматирующих токенов."""
    return {
        "strong_open": ("**", "**"),
        "em_open": ("*", "*"),
        "s_open": ("~~", "~~"),
        "del_open": ("~~", "~~"),
    }.get(token_type)


def extract_translatable_segments(
    inline_token: Token,
) -> list[InlineSegment]:
    """
    Разбирает inline-токен на сегменты.

    Текстовые сегменты помечаются translatable=True.
    Форматирование (**, *, ~~) становится prefix/suffix соседнего текста.
    Нетекстовые элементы (код, ссылки, изображения) — translatable=False.
    """
    children = inline_token.children or []
    segments: list[InlineSegment] = []

    # Стек открытых форматирующих тегов: (open_tag, close_tag)
    fmt_stack: list[tuple[str, str]] = []

    i = 0
    while i < len(children):
        token = children[i]

        match token.type:
            # ── текст ────────────────────────────────────────────────────────
            case "text":
                text = token.content
                if text.strip():
                    # Собираем prefix из открытых форматов
                    prefix = "".join(t[0] for t in fmt_stack)
                    suffix = "".join(t[1] for t in reversed(fmt_stack))
                    segments.append(
                        InlineSegment(
                            text=text,
                            translatable=True,
                            prefix=prefix,
                            suffix=suffix,
                        )
                    )
                    # После извлечения текста — форматирование "использовано"
                    fmt_stack.clear()

            # ── форматирование: открывающий тег ──────────────────────────────
            case "strong_open" | "em_open" | "s_open" | "del_open":
                tags = _get_fmt_tags(token.type)
                if tags:
                    fmt_stack.append(tags)

            # ── форматирование: закрывающий тег — игнорируем, суффикс уже в сегменте
            case "strong_close" | "em_close" | "s_close" | "del_close":
                # Если стек не пуст, значит текст между тегами был пустым
                if fmt_stack:
                    fmt_stack.pop()

            # ── inline-код ───────────────────────────────────────────────────
            case "code_inline":
                segments.append(
                    InlineSegment(
                        text=f"`{token.content}`",
                        translatable=False,
                    )
                )
                fmt_stack.clear()

            # ── ссылки ───────────────────────────────────────────────────────
            case "link_open":
                # Собираем всё содержимое ссылки до link_close
                href = token.attrGet("href") or ""
                title = token.attrGet("title") or ""
                link_texts: list[str] = []
                i += 1
                while i < len(children) and children[i].type != "link_close":
                    if children[i].type == "text":
                        link_texts.append(children[i].content)
                    i += 1
                link_text = " ".join(link_texts)
                if title:
                    md = f'[{link_text}]({href} "{title}")'
                else:
                    md = f"[{link_text}]({href})"
                segments.append(
                    InlineSegment(
                        text=md,
                        translatable=False,
                    )
                )
                fmt_stack.clear()

            # ── изображение ──────────────────────────────────────────────────
            case "image":
                src = token.attrGet("src") or ""
                alt = token.content or ""
                segments.append(
                    InlineSegment(
                        text=f"![{alt}]({src})",
                        translatable=False,
                    )
                )
                fmt_stack.clear()

            # ── переносы ─────────────────────────────────────────────────────
            case "softbreak":
                segments.append(InlineSegment(text=" ", translatable=False))

            case "hardbreak":
                segments.append(InlineSegment(text="  \n", translatable=False))

            case "html_inline":
                segments.append(
                    InlineSegment(
                        text=token.content,
                        translatable=False,
                    )
                )

        i += 1

    return segments


def render_segments(
    segments: list[InlineSegment],
    translate_fn: TranslateFunc,
) -> str:
    """
    Переводит каждый сегмент с translatable=True,
    нетекстовые — оставляет как есть.
    Возвращает итоговую строку.
    """
    parts: list[str] = []
    for seg in segments:
        if seg.translatable and seg.text.strip():
            translated = translate_fn(seg.text)
            parts.append(f"{seg.prefix}{translated}{seg.suffix}")
        else:
            parts.append(seg.text)
    return "".join(parts)
