from __future__ import annotations

from markdown_it.token import Token

from mt_server.markdown.units import Placeholder


class PlaceholderRegistry:
    def __init__(self):
        self._counter = 0

    def next(self, prefix: str = "x") -> str:
        value = f"<{prefix}{self._counter}/>"
        self._counter += 1
        return value


INLINE_CODE_TOKEN_TYPES = {
    "code_inline",
}


LINK_OPEN_TOKEN_TYPES = {
    "link_open",
}


IMAGE_TOKEN_TYPES = {
    "image",
}


FORMATTING_TOKEN_TYPES = {
    "strong_open",
    "strong_close",
    "em_open",
    "em_close",
}


class InlinePlaceholderExtractor:
    def __init__(self):
        self.registry = PlaceholderRegistry()

    def extract(self, inline_token: Token) -> tuple[str, list[Placeholder]]:
        placeholders: list[Placeholder] = []
        result: list[str] = []

        children = inline_token.children or []

        for token in children:
            match token.type:
                case "text":
                    result.append(token.content)

                case "strong_open":
                    result.append("<b>")

                case "strong_close":
                    result.append("</b>")

                case "em_open":
                    result.append("<i>")

                case "em_close":
                    result.append("</i>")

                case "code_inline":
                    placeholder = self.registry.next("code")

                    placeholders.append(
                        Placeholder(
                            key=placeholder,
                            kind="inline_code",
                            value=token.content,
                        )
                    )

                    result.append(placeholder)

                case "link_open":
                    href = token.attrGet("href")

                    placeholder = self.registry.next("link")

                    placeholders.append(
                        Placeholder(
                            key=placeholder,
                            kind="link_href",
                            value=href,
                        )
                    )

                    result.append(placeholder)

                case "link_close":
                    result.append("</link>")

                case "image":
                    src = token.attrGet("src")
                    alt = token.content or ""

                    placeholder = self.registry.next("img")

                    placeholders.append(
                        Placeholder(
                            key=placeholder,
                            kind="image_src",
                            value=src,
                        )
                    )

                    result.append(f"{placeholder}{alt}")

                case _:
                    if token.content:
                        result.append(token.content)

        return "".join(result).strip(), placeholders
