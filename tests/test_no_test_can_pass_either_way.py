"""No test in this suite is allowed to be green whichever way the code goes.

`@pytest.mark.xfail(strict=False)` makes both outcomes pass: the test is green
when the code is broken, and green again when it is fixed. It is then counted in
the total while asserting nothing, which is worse than not having it, because
the total is what people read.

Two things hold the line, and this file checks both rather than trusting either.

* `xfail_strict = true` in `pyproject.toml` makes an unmarked `xfail` strict, so
  a test that starts passing unexpectedly fails until someone removes the mark.
  That is the default for anything written from here on.
* Writing `strict=False` explicitly overrides the setting, so the setting alone
  is not enough. Nothing here may do it.

A genuinely known, genuinely unfixed gap is still expressible: `xfail` under the
strict setting, or `pytest.skip` with the reason, both of which say out loud that
the case is not being checked. What is not available is a case that reports
success either way.
"""

import ast
import tomllib
from pathlib import Path

TESTS = Path("tests")
PYPROJECT = Path("pyproject.toml")


def test_xfail_strict_is_on_by_default():
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    ini = config["tool"]["pytest"]["ini_options"]
    assert ini.get("xfail_strict") is True, (
        "`xfail_strict` is not true in pyproject.toml, so an `xfail` with no "
        "`strict=` passes whether the code works or not"
    )


def _turns_strictness_off(node: ast.AST) -> bool:
    """A call passing a literal `strict=False`.

    Read from the syntax tree rather than the file's text, so prose that
    discusses the setting — this file's own docstring, for one — is not mistaken
    for code that uses it.
    """
    if not isinstance(node, ast.Call):
        return False
    return any(
        kw.arg == "strict" and isinstance(kw.value, ast.Constant) and kw.value.value is False
        for kw in node.keywords
    )


def test_no_test_file_turns_strictness_off():
    offenders = []
    for path in sorted(TESTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if _turns_strictness_off(node):
                offenders.append(f"{path}:{node.lineno}: {ast.unparse(node)}")
    assert not offenders, (
        "these switch strictness off, so the test passes whether the code works "
        "or not:\n" + "\n".join(offenders)
    )
