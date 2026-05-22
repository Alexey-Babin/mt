from markdown_it import MarkdownIt


def ast_equal(a: str, b: str) -> bool:
    md = MarkdownIt()

    a_tokens = [(t.type, t.tag) for t in md.parse(a)]
    b_tokens = [(t.type, t.tag) for t in md.parse(b)]

    return a_tokens == b_tokens
