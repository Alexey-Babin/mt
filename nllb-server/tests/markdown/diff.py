from markdown_it import MarkdownIt


def ast_equal(a: str, b: str, rules: dict | None = None) -> bool:
    """
    Compare markdown AST structures.

    Rules:
    - compare_ast_structure: if False, skip structure comparison (for malformed input)
    - strict_text_equality: if True, require exact text match
    - preserve_frontmatter: if True, YAML frontmatter should be preserved
    - preserve_mixed_content: if True, HTML tags should be preserved
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

    # Check if frontmatter should be preserved
    if rules.get("preserve_frontmatter"):
        # Extract and compare frontmatter separately
        a_lines = a.split("\n")
        b_lines = b.split("\n")

        if a_lines[0].strip() == "---":
            # Find end of frontmatter in input
            a_end = 1
            for i in range(1, len(a_lines)):
                if a_lines[i].strip() == "---":
                    a_end = i + 1
                    break

            # Find end of frontmatter in output
            b_end = 1
            for i in range(1, len(b_lines)):
                if b_lines[i].strip() == "---":
                    b_end = i + 1
                    break

            # Frontmatter should be preserved exactly
            a_frontmatter = "\n".join(a_lines[:a_end])
            b_frontmatter = "\n".join(b_lines[:b_end])
            if a_frontmatter != b_frontmatter:
                return False

            # Compare only the content after frontmatter
            a_content = "\n".join(a_lines[a_end:])
            b_content = "\n".join(b_lines[b_end:])
            a_tokens = list(md.parse(a_content))
            b_tokens = list(md.parse(b_content))

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
