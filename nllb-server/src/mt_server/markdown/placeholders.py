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


class InlinePlaceholderExtractor:
    def __init__(self):
        self.registry = PlaceholderRegistry()

    def extract(self, inline_token: Token) -> tuple[str, list[Placeholder]]:
        placeholders: list[Placeholder] = []
        result: list[str] = []

        children = inline_token.children or []

        i = 0
        while i < len(children):
            token = children[i]

            match token.type:
                case "text":
                    result.append(token.content)
                    i += 1

                case "strong_open":
                    result.append("**")
                    i += 1

                case "strong_close":
                    result.append("**")
                    i += 1

                case "em_open":
                    result.append("*")
                    i += 1

                case "em_close":
                    result.append("*")
                    i += 1

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
                    i += 1

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
                    result.append(f"[{placeholder}")

                    # Найдём соответствующий link_close и текст между ними
                    text_content = []
                    j = i + 1
                    while j < len(children) and children[j].type != "link_close":
                        if children[j].type == "text":
                            text_content.append(children[j].content)
                        j += 1

                    if text_content:
                        result.append("".join(text_content))

                    result.append("]")
                    i = j + 1 if j < len(children) else i + 1

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
                    result.append(f"![{alt}]({placeholder})")
                    i += 1

                case _:
                    if token.content:
                        result.append(token.content)
                    i += 1

        return "".join(result).strip(), placeholders
