"""Coverage has to follow the CLI tests into their subprocesses.

`app/rules/__main__.py` and `app/vision/__main__.py` are command-line entry
points, and the only honest test of one runs it the way a person does. Four
tests do, in subprocesses. Coverage measures the process it starts in, so at first
it saw none of that and reported both modules at 0% — which reads as
"nobody tests these" when the truth was "coverage cannot see these being
tested". A wrong 0% is worse than no figure: it points effort at the one place
that does not need it.

Two settings make it work, and either one alone does nothing. This file holds
both, because the failure they prevent is silent: remove one and the suite goes
on passing while the figure quietly returns to 0%.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _coverage_run_config() -> dict:
    with (_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["tool"]["coverage"]["run"]


def test_coverage_writes_one_data_file_per_process() -> None:
    """`parallel` lets a subprocess write its own data file instead of racing
    the parent for one. Without it the subprocess measurement is lost even
    when it is collected."""
    assert _coverage_run_config().get("parallel") is True


def test_the_suite_turns_on_subprocess_measurement_for_whoever_runs_it() -> None:
    """`coverage` starts measuring in a subprocess only when
    `COVERAGE_PROCESS_START` names a config file. The session fixture in
    `tests/conftest.py` sets it, so the figure is right for CI and for anyone
    who clones this, rather than right only for whoever knew to export it.
    """
    conftest = (_ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "COVERAGE_PROCESS_START" in conftest, (
        "tests/conftest.py no longer sets COVERAGE_PROCESS_START, so coverage "
        "will report the two __main__ modules at 0% again"
    )
