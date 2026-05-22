from __future__ import annotations

import logging
from dataclasses import dataclass

from markdown_it.token import Token

from mt_server.markdown.units import Placeholder

logger = logging.getLogger("uvicorn.error")


class PlaceholderRegistry:
    def __init__(self):
        self._counter = 0

    def next(self, prefix: str = "x") -> str:
        value = f"\x02{prefix}{self._counter}\x03"
        self._counter += 1
        return value


@dataclass
class SpanMarker:
    """Маркер открывающего/закрывающего тега форматирования"""

    placeholder: str  # ключ-заменитель, вставленный в текст
    open_tag: str  # исходный открывающий тег, напр. "**"
    close_tag: str  # исходный закрывающий тег, напр. "**"
    is_open: bool  # это открывающий или закрывающий маркер


class InlinePlaceholderExtractor:
    """
    Извлекает текст из inline-токена, заменяя:
    - inline-код          → placeholder  (вид: \x02codeN\x03)
    - форматирование      → placeholder  (вид: \x02fmtN\x03)
    - ссылки/изображения  → сохраняются как placeholder

    Переводчику уходит чистый текст с нейтральными маркерами.
    После перевода MarkdownRestorer восстанавливает исходные теги.
    """

    def __init__(self):
        self.registry = PlaceholderRegistry()

    def extract(self, inline_token: Token) -> tuple[str, list[Placeholder]]:
        placeholders: list[Placeholder] = []
        result: list[str] = []

        children = inline_token.children or []

        logger.debug(f"Processing inline token with {len(children)} children")

        # Стек открытых span-маркеров: (placeholder_key, open_tag, close_tag)
        open_stack: list[tuple[str, str, str]] = []

        for token in children:
            logger.debug(
                f"  Child token: type={token.type!r}, content={token.content!r}"
            )

            match token.type:
                case "text" | "html_inline":
                    result.append(token.content)

                # ── жирный ──────────────────────────────────────────────────
                case "strong_open":
                    key = self.registry.next("fmt")
                    open_stack.append((key, "**", "**"))
                    placeholders.append(
                        Placeholder(key=key, kind="fmt_open", value="**")
                    )
                    result.append(key)

                case "strong_close":
                    if open_stack:
                        open_key, open_tag, close_tag = open_stack.pop()
                        key = self.registry.next("fmt")
                        placeholders.append(
                            Placeholder(
                                key=key,
                                kind="fmt_close",
                                value={"open_key": open_key, "tag": close_tag},
                            )
                        )
                        result.append(key)

                # ── курсив ───────────────────────────────────────────────────
                case "em_open":
                    key = self.registry.next("fmt")
                    open_stack.append((key, "*", "*"))
                    placeholders.append(
                        Placeholder(key=key, kind="fmt_open", value="*")
                    )
                    result.append(key)

                case "em_close":
                    if open_stack:
                        open_key, open_tag, close_tag = open_stack.pop()
                        key = self.registry.next("fmt")
                        placeholders.append(
                            Placeholder(
                                key=key,
                                kind="fmt_close",
                                value={"open_key": open_key, "tag": close_tag},
                            )
                        )
                        result.append(key)

                # ── зачёркивание (~~) ────────────────────────────────────────
                case "s_open" | "del_open":
                    key = self.registry.next("fmt")
                    open_stack.append((key, "~~", "~~"))
                    placeholders.append(
                        Placeholder(key=key, kind="fmt_open", value="~~")
                    )
                    result.append(key)

                case "s_close" | "del_close":
                    if open_stack:
                        open_key, open_tag, close_tag = open_stack.pop()
                        key = self.registry.next("fmt")
                        placeholders.append(
                            Placeholder(
                                key=key,
                                kind="fmt_close",
                                value={"open_key": open_key, "tag": close_tag},
                            )
                        )
                        result.append(key)

                # ── inline-код ───────────────────────────────────────────────
                case "code_inline":
                    key = self.registry.next("code")
                    placeholders.append(
                        Placeholder(key=key, kind="inline_code", value=token.content)
                    )
                    result.append(key)

                # ── ссылка ───────────────────────────────────────────────────
                case "link_open":
                    href = token.attrGet("href") or ""
                    title = token.attrGet("title") or ""
                    key = self.registry.next("lnk")
                    placeholders.append(
                        Placeholder(
                            key=key,
                            kind="link_open",
                            value={"href": href, "title": title},
                        )
                    )
                    result.append(key)

                case "link_close":
                    key = self.registry.next("lnk")
                    placeholders.append(
                        Placeholder(key=key, kind="link_close", value=None)
                    )
                    result.append(key)

                # ── изображение ──────────────────────────────────────────────
                case "image":
                    src = token.attrGet("src") or ""
                    alt = token.content or ""
                    key = self.registry.next("img")
                    placeholders.append(
                        Placeholder(
                            key=key, kind="image", value={"src": src, "alt": alt}
                        )
                    )
                    result.append(key)

                # ── мягкий / жёсткий перенос строки ─────────────────────────
                case "softbreak":
                    result.append(" ")

                case "hardbreak":
                    key = self.registry.next("br")
                    placeholders.append(
                        Placeholder(key=key, kind="hardbreak", value=None)
                    )
                    result.append(key)

                case _:
                    if token.content:
                        result.append(token.content)

        final_text = "".join(result).strip()
        logger.debug(f"Final extracted text: {final_text!r}")

        return final_text, placeholders
