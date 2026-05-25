import re

from markdown_it import MarkdownIt


def ast_equal(a: str, b: str, rules: dict | None = None) -> bool:
    """
    Compare markdown AST structures.

    Rules:
    - compare_ast_structure: if False, skip structure comparison (for malformed input)
    - strict_text_equality: if True, require exact text match
    - preserve_frontmatter: if True, YAML frontmatter should be preserved
    - preserve_mixed_content: if True, HTML tags should be preserved
    - preserve_code_blocks: if True, code blocks should be preserved exactly
    - preserve_language_identifier: if True, language identifiers in code blocks should be preserved
    - translate_code_comments: if True, comments in code can be translated
    - translate_strings_in_code: if True, strings in code can be translated
    - preserve_html_tags: if True, HTML tags should be preserved exactly
    """
    if rules is None:
        rules = {}

    # If structure comparison is disabled, just check basic sanity
    if not rules.get("compare_ast_structure", True):
        # For malformed input, just verify we got some output
        return len(b.strip()) > 0

    md = MarkdownIt()

    # a_tokens = [(t.type, t.tag) for t in md.parse(a)]
    # b_tokens = [(t.type, t.tag) for t in md.parse(b)]

    # return a_tokens == b_tokens
    a_tokens = list(md.parse(a))
    b_tokens = list(md.parse(b))

    # Check if code blocks should be preserved
    if rules.get("preserve_code_blocks"):
        # Extract code blocks from input and verify they exist in output
        # Find all code blocks in input with their language identifiers
        code_block_pattern = r"```(\w*)\n(.*?)```"
        a_code_blocks = re.findall(code_block_pattern, a, re.DOTALL)
        b_code_blocks = re.findall(code_block_pattern, b, re.DOTALL)

        # Code blocks should be preserved exactly
        if a_code_blocks != b_code_blocks:
            return False

        # Remove code blocks from both texts for further comparison
        a_without_code = re.sub(code_block_pattern, "", a, flags=re.DOTALL)
        b_without_code = re.sub(code_block_pattern, "", b, flags=re.DOTALL)

        # Compare the remaining content
        a_tokens = list(md.parse(a_without_code))
        b_tokens = list(md.parse(b_without_code))

    # Check if HTML tags should be preserved
    if rules.get("preserve_html_tags"):
        # Extract HTML tags from input and output
        html_tag_pattern = r"<[^>]+>"
        a_html_tags = re.findall(html_tag_pattern, a)
        b_html_tags = re.findall(html_tag_pattern, b)

        # HTML tags should be preserved exactly
        if a_html_tags != b_html_tags:
            return False

        # Remove HTML tags from both texts for further comparison
        a_without_html = re.sub(html_tag_pattern, "", a)
        b_without_html = re.sub(html_tag_pattern, "", b)

        # Compare the remaining content
        a_tokens = list(md.parse(a_without_html))
        b_tokens = list(md.parse(b_without_html))

    # Compare token types and tags
    a_structure = [(t.type, t.tag) for t in a_tokens]
    b_structure = [(t.type, t.tag) for t in b_tokens]

    if a_structure != b_structure:
        return False

    # If strict text equality is required
    if rules.get("strict_text_equality", False):
        a_text = " ".join(t.content for t in a_tokens if hasattr(t, "content"))
        b_text = " ".join(t.content for t in b_tokens if hasattr(t, "content"))
        return a_text == b_text

    return True
