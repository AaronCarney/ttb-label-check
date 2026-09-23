"""The local checks run what a reviewer is told they run.

The suite once ran only when a person typed the command, which is how seven
browser tests failed unnoticed for days. `scripts/ci.sh` fixes that only if it
runs every check, stops at the first one that fails, and is what a push and a
deploy are held to. These tests read the script and the hook rather than
trusting the README's account of them, and drive the hook as a black box.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
CI_SCRIPT = ROOT / "scripts/ci.sh"
HOOK = ROOT / ".githooks/pre-push"

# Each command is the one the README's "Linting, formatting and type checking"
# section tells a reader to run, plus the suite itself with its coverage.
REQUIRED_COMMANDS = (
    "ruff check",
    "ruff format --check",
    "mypy",
    "pytest",
    "--cov",
)


@pytest.mark.parametrize("command", REQUIRED_COMMANDS)
def test_the_script_runs_each_check(command: str) -> None:
    lines = [
        line.strip()
        for line in CI_SCRIPT.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("uv run ")
    ]
    assert any(command in line for line in lines), (
        f"{CI_SCRIPT.name} runs no `{command}`; a check nothing runs is not a check"
    )


def test_a_failing_check_stops_the_script() -> None:
    """Without `set -e` a failing lint scrolls past and the pass is recorded
    anyway, which is the same defect as a test that cannot fail."""
    assert "set -euo pipefail" in CI_SCRIPT.read_text(encoding="utf-8")


def test_no_hosted_pipeline_spends_runner_minutes() -> None:
    """The checks run here (decision 0067). A pipeline file would have GitLab
    run them again on every push, on a quota that has already run out once."""
    assert not (ROOT / ".gitlab-ci.yml").exists()


def _head(offset: str = "") -> str:
    return subprocess.run(
        ["git", "rev-parse", f"HEAD{offset}"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _push(tmp_path: Path, sha: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(HOOK), "origin", "https://example.invalid/repo.git"],
        cwd=ROOT,
        input=f"refs/heads/main {sha} refs/heads/main {'0' * 40}\n",
        capture_output=True,
        text=True,
        env={**os.environ, "TTB_CI_RECORD_DIR": str(tmp_path)},
    )


def test_the_hook_lets_a_checked_commit_through(tmp_path: Path) -> None:
    sha = _head("~1")
    (tmp_path / sha).touch()
    result = _push(tmp_path, sha)
    assert result.returncode == 0, result.stderr


def test_the_hook_refuses_an_unchecked_commit_it_cannot_check(tmp_path: Path) -> None:
    """A commit other than HEAD cannot be checked from the checked-out tree, so
    it is refused rather than run, and the refusal says what to do. HEAD itself
    would start the whole suite, which this test must not do from inside it."""
    result = _push(tmp_path, _head("~1"))
    assert result.returncode != 0
    assert "scripts/ci.sh" in result.stderr


def test_a_deleted_branch_pushes_no_commit(tmp_path: Path) -> None:
    result = _push(tmp_path, "0" * 40)
    assert result.returncode == 0, result.stderr
