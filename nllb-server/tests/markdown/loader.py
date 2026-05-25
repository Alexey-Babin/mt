import json
from pathlib import Path

# BASE = Path("/opt/mt/data/markdown-tests")
BASE = Path(__file__).parent.parent.parent.parent / "data" / "markdown-tests"


def load_cases():
    cases = []

    for test_dir in BASE.iterdir():
        if not test_dir.is_dir():
            continue

        input_md = (test_dir / "input.md").read_text()
        expected_md = (test_dir / "expected.md").read_text()
        rules = json.loads((test_dir / "rules.json").read_text())

        cases.append(
            {
                "name": test_dir.name,
                "input": input_md,
                "expected": expected_md,
                "rules": rules,
            }
        )

    return cases
