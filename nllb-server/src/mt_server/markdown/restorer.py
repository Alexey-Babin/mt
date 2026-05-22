from __future__ import annotations

import logging

from markdown_it import MarkdownIt
from markdown_it.token import Token

from mt_server.markdown.units import TranslationUnit

logger = logging.getLogger("uvicorn.error")


class MarkdownRestorer:
    """
    Восстанавливает Markdown после перевода.

    Переведённый текст уже содержит финальную строку (с разметкой),
    поэтому просто обновляем inline-токен.
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
            logger.debug(f"Restoring unit {unit.id}: {unit.text!r}")
            _set_inline_content(token, unit.text)

        renderer = self.md.renderer
        return renderer.render(tokens, self.md.options, {})


def _set_inline_content(token: Token, text: str) -> None:
    """
    Обновляет inline-токен новым текстом.
    markdown-it рендерит через children, поэтому заменяем их.
    """
    token.content = text
    new_child = Token("text", "", 0)
    new_child.content = text
    token.children = [new_child]
