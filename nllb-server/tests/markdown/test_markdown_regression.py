import pytest
from tests.markdown.diff import ast_equal
from tests.markdown.loader import load_cases
from tests.markdown.runner import run_translation

cases = load_cases()


@pytest.mark.parametrize("case", cases, ids=lambda c: c["name"])
def test_markdown(case):
    output = run_translation(case["input"])
    assert ast_equal(case["expected"], output, case.get("rules", {}))
