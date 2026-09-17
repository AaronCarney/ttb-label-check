# tests/test_evaluator_chokepoint_grep.py
"""The Evaluator never raises: it is the chokepoint, and it catches everything,
so a failure anywhere below it comes back as a needs_review result rather than a
500. Two exceptions are allowed in the source — a NotImplementedError, and a
raise preceded by a `# programmer error` comment within two lines."""
import re
from pathlib import Path

_RAISE_RX = re.compile(r"^\s*raise\s+(\S+)")


def test_evaluator_has_no_bare_raise():
    src = Path("app/services/evaluator.py").read_text()
    lines = src.splitlines()
    violations: list[str] = []
    for i, line in enumerate(lines, start=1):
        m = _RAISE_RX.match(line)
        if not m:
            continue
        what = m.group(1)
        if "NotImplementedError" in what:
            continue
        prior_2 = "\n".join(lines[max(0, i - 3):i - 1]).lower()
        if "programmer error" in prior_2 or "programmer-error" in prior_2:
            continue
        violations.append(f"L{i}: {line.strip()}")
    assert not violations, "P4 violation — bare raise in evaluator.py:\n" + "\n".join(violations)
