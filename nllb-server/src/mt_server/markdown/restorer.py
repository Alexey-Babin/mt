from __future__ import annotations

import logging

from markdown_it import MarkdownIt
from markdown_it.token import Token

from mt_server.markdown.units import Placeholder, TranslationUnit

logger = logging.getLogger("uvicorn.error")


class MarkdownRestorer:
    """
    Восстанавливает Markdown-текст после перевода:
    1. Заменяет placeholder-ключи обратно на markdown-разметку
    2. Обновляет token.children так, чтобы рендерер видел новый текст
    """

    def __init__(self):
        self.md = MarkdownIt("commonmark", {"html": False})

    def restore(
        self,
        tokens: list[Token],
        units: list[TranslationUnit],
    ) -> str:
        for unit in units:
            token = tokens[unit.inline_token_index]
            restored = _restore_placeholders(unit.text, unit.placeholders)
            logger.debug(f"Restoring unit {unit.id}: {unit.text!r} → {restored!r}")
            _set_inline_content(token, restored)

        renderer = self.md.renderer
        return renderer.render(tokens, self.md.options, {})


# ──────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────────────


def _restore_placeholders(text: str, placeholders: list[Placeholder]) -> str:
    """
    Заменяет нейтральные ключи (\x02…\x03) на оригинальную markdown-разметку.
    """
    result = text

    # Собираем map key → replacement
    replacements: dict[str, str] = {}

    for ph in placeholders:
        match ph.kind:
            case "inline_code":
                replacements[ph.key] = f"`{ph.value}`"

            case "fmt_open":
                # ph.value — сам тег, напр. "**"
                replacements[ph.key] = ph.value

            case "fmt_close":
                # ph.value = {"open_key": ..., "tag": "**"}
                replacements[ph.key] = ph.value["tag"]

            case "link_open":
                href = ph.value.get("href", "")
                title = ph.value.get("title", "")
                if title:
                    replacements[ph.key] = "[" + "\x01LINK_TEXT\x01"  # заглушка
                else:
                    replacements[ph.key] = "["

            case "link_close":
                replacements[ph.key] = "]"

            case "image":
                src = ph.value.get("src", "")
                alt = ph.value.get("alt", "")
                replacements[ph.key] = f"![{alt}]({src})"

            case "hardbreak":
                replacements[ph.key] = "  \n"

    for key, replacement in replacements.items():
        result = result.replace(key, replacement)

    return result


def _set_inline_content(token: Token, text: str) -> None:
    """
    Обновляет inline-токен так, чтобы рендерер использовал новый текст.

    markdown-it рендерит inline-токены через children, а не через content.
    Поэтому мы заменяем children на единственный text-токен.
    """
    token.content = text

    new_child = Token("text", "", 0)
    new_child.content = text
    token.children = [new_child]
