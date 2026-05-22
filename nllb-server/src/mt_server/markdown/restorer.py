from __future__ import annotations

from markdown_it import MarkdownIt
from markdown_it.token import Token

from mt_server.markdown.units import Placeholder, TranslationUnit


class MarkdownRestorer:
    """Восстанавливает Markdown с переведённым текстом и placeholders"""

    def __init__(self):
        self.md = MarkdownIt("commonmark", {"html": False})

    def restore(
        self,
        tokens: list[Token],
        units: list[TranslationUnit],
    ) -> str:
        """Восстанавливает финальный Markdown после перевода"""

        # Применяем переводы к токенам
        for unit in units:
            token = tokens[unit.inline_token_index]

            # Восстанавливаем текст с placeholders
            restored_text = self._restore_placeholders(unit.text, unit.placeholders)
            token.content = restored_text

            # Очищаем children для корректной рендеринга
            if token.children:
                token.children = None

        # Рендерим в HTML
        renderer = self.md.renderer
        return renderer.render(tokens, self.md.options, {})

    @staticmethod
    def _restore_placeholders(
        text: str,
        placeholders: list[Placeholder],
    ) -> str:
        """Заменяет плейсхолдеры на оригинальные значения"""
        result = text

        for placeholder in placeholders:
            match placeholder.kind:
                case "inline_code":
                    result = result.replace(placeholder.key, f"`{placeholder.value}`")
                case "link_href":
                    result = result.replace(placeholder.key, placeholder.value)
                case "image_src":
                    result = result.replace(placeholder.key, placeholder.value)

        return result
