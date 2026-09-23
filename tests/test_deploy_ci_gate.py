"""A deploy must not be able to ship a commit nothing has tested.

`scripts/deploy.sh`'s preflights answer only whether the repository is
*shippable*: a Dockerfile, a service port matching the container's, a tracked
island bundle, every COPY path present. Not one of them runs a test.
`scripts/ci.sh` runs the lint, the formatter, the type check and the whole suite
and records a pass against the commit it tested (decision 0067). These tests
drive the real script with a stubbed `gcloud` and a record directory of their
own, so what is checked is what the script does with that record rather than
what it says it does.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/deploy.sh"


def _rev(ref: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", ref], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def run_deploy(tmp_path: Path):
    """Run the real deploy script with `gcloud` stubbed out.

    The stub shadows the real binary by sitting first on PATH and records every
    invocation to a file, so "nothing was deployed" is checked by the absence of
    a deploy rather than by the script's own wording.
    """
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    records = tmp_path / "ci-passed"
    records.mkdir()
    deploys = tmp_path / "gcloud-calls"
    gcloud = stubs / "gcloud"
    gcloud.write_text(f'#!/usr/bin/env bash\necho "$@" >> "{deploys}"\nexit 0\n')
    gcloud.chmod(0o755)

    def run(*checked: str, **env: str) -> subprocess.CompletedProcess[str]:
        for sha in checked:
            (records / sha).touch()
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
                "TTB_GCP_PROJECT": "a-project-that-does-not-exist",
                "TTB_CI_RECORD_DIR": str(records),
                **env,
            },
        )
        result.deployed = "run deploy" in deploys.read_text() if deploys.exists() else False  # type: ignore[attr-defined]
        return result

    return run


def test_a_checked_commit_is_deployed(run_deploy) -> None:
    """The gate is a gate, not a wall: the case it must allow is the normal one."""
    result = run_deploy(_rev("HEAD"))
    assert result.returncode == 0, result.stderr
    assert result.deployed, "a commit scripts/ci.sh passed was not deployed"


def test_a_pass_for_another_commit_does_not_count(run_deploy) -> None:
    """`git archive HEAD` is what gets uploaded, so only HEAD's pass answers for
    it. A pass recorded for the commit before says nothing about this one."""
    result = run_deploy(_rev("HEAD~1"))
    assert result.returncode != 0
    assert not result.deployed


def test_an_unchecked_commit_stops_the_deploy(run_deploy) -> None:
    """The refusal has to say that running the checks is the fix, because a
    reader who is told only "not tested" will reach for the override."""
    result = run_deploy()
    assert result.returncode != 0
    assert not result.deployed
    assert "scripts/ci.sh" in result.stderr, f"the refusal does not say what to do: {result.stderr}"


def test_the_override_deploys_but_says_what_it_does_not_know(run_deploy) -> None:
    """Using the escape hatch is only safe if it is on the record: the terminal
    has to say that nothing tested what was shipped."""
    result = run_deploy(TTB_SKIP_CI_CHECK="1")
    assert result.returncode == 0, result.stderr
    assert result.deployed
    assert "TTB_SKIP_CI_CHECK" in result.stderr
    assert "nothing has tested" in result.stderr.lower()


def test_check_only_needs_no_record_and_no_network(tmp_path: Path) -> None:
    """`--check` proves the repository is deployable, which it can be before
    its checks have run, and it needs no network. `gcloud` is replaced by a stub
    that fails if it is run at all, and no record directory exists, so this
    passes only because `--check` stops before both."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    stub = stubs / "gcloud"
    stub.write_text('#!/usr/bin/env bash\necho "--check ran gcloud" >&2\nexit 99\n')
    stub.chmod(0o755)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
            "TTB_CI_RECORD_DIR": str(tmp_path / "absent"),
        },
    )
    assert result.returncode == 0, f"--check failed: {result.stderr}"
    assert "--check ran" not in result.stderr, result.stderr
