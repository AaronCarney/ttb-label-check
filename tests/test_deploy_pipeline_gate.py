"""A deploy must not be able to ship a commit nothing has tested.

Until 2026-09-17 `scripts/deploy.sh` was typed by a person and its preflights
answered only whether the repository was *shippable*: a Dockerfile, a service
port matching the container's, a tracked island bundle, every COPY path
present. Not one of them ran a test, so whether the code worked rested on
whether whoever typed the command had remembered to run the suite. A commit
that had never left the machine it was written on deployed exactly as readily
as one the pipeline had passed.

`.gitlab-ci.yml` already runs the lint, the formatter, the type check and the
whole suite, and its verdict is attached to a SHA. These tests drive the real
script with a stubbed `glab` and `gcloud`, so what is checked is what the
script does with that verdict rather than what it says it does.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/deploy.sh"


def _pipeline(status: str) -> str:
    return json.dumps(
        [{"status": status, "web_url": "https://gitlab.example/pipelines/1", "sha": "x"}]
    )


@pytest.fixture
def run_deploy(tmp_path: Path):
    """Run the real deploy script with `glab` and `gcloud` stubbed out.

    The stubs shadow the real binaries by sitting first on PATH. `gcloud`
    records every invocation to a file, so "nothing was deployed" is checked by
    the absence of a deploy rather than by the script's own wording.
    """
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    deploys = tmp_path / "gcloud-calls"
    asked = tmp_path / "glab-asked"

    def _stub(name: str, body: str) -> None:
        path = stubs / name
        path.write_text(f"#!/usr/bin/env bash\n{body}\n")
        path.chmod(0o755)

    _stub("gcloud", f'echo "$@" >> "{deploys}"\nexit 0')

    def run(pipelines: str, **env: str) -> subprocess.CompletedProcess[str]:
        _stub("glab", f'echo "$@" >> "{asked}"\ncat <<\'JSON\'\n{pipelines}\nJSON')
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
                "TTB_GCP_PROJECT": "a-project-that-does-not-exist",
                **env,
            },
        )
        result.deployed = "run deploy" in deploys.read_text() if deploys.exists() else False  # type: ignore[attr-defined]
        result.asked = asked.read_text() if asked.exists() else ""  # type: ignore[attr-defined]
        return result

    return run


def test_a_passing_pipeline_lets_the_deploy_through(run_deploy) -> None:
    """The gate is a gate, not a wall: the case it must allow is the normal one."""
    result = run_deploy(_pipeline("success"))
    assert result.returncode == 0, result.stderr
    assert result.deployed, "a commit whose pipeline passed was not deployed"


def test_the_verdict_is_read_for_the_commit_being_deployed(run_deploy) -> None:
    """`git archive HEAD` is what gets uploaded, so HEAD's verdict is the only
    one that answers for it. A pipeline that passed on some other commit says
    nothing about this one."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    result = run_deploy(_pipeline("success"))
    assert head in result.asked, f"the pipeline was not looked up for HEAD ({head}): {result.asked}"


@pytest.mark.parametrize("status", ["failed", "canceled", "running", "pending", "manual"])
def test_a_pipeline_that_has_not_passed_stops_the_deploy(run_deploy, status: str) -> None:
    """Anything short of success is a refusal, including a run still going. A
    pipeline that has not finished has not passed, and waiting for it is cheap
    next to a broken revision."""
    result = run_deploy(_pipeline(status))
    assert result.returncode != 0, f"a {status} pipeline did not stop the deploy"
    assert not result.deployed, f"a {status} pipeline still reached gcloud run deploy"


def test_a_commit_with_no_pipeline_at_all_stops_the_deploy(run_deploy) -> None:
    """The common case, not an edge one: a commit that has not been pushed has
    been tested by nothing but the machine it was written on. The message has
    to say that pushing is the fix, because a reader who is told only "no
    pipeline" will reach for the override."""
    result = run_deploy("[]")
    assert result.returncode != 0
    assert not result.deployed
    assert "push" in result.stderr.lower(), f"the refusal does not say what to do: {result.stderr}"


def test_the_override_deploys_but_says_what_it_does_not_know(run_deploy) -> None:
    """An escape hatch is needed for a deploy that has to go out while GitLab
    is unreachable, and it is only safe if using it is on the record: the
    terminal has to say that nothing tested what was shipped."""
    result = run_deploy(_pipeline("failed"), TTB_SKIP_PIPELINE_CHECK="1")
    assert result.returncode == 0, result.stderr
    assert result.deployed
    assert "TTB_SKIP_PIPELINE_CHECK" in result.stderr
    assert "nothing has tested" in result.stderr.lower()


def test_check_only_still_needs_no_network(tmp_path: Path) -> None:
    """`--check` is documented as the preflights that need no network, and it
    is what proves the repository is deployable without touching anything. The
    gate must stay below it: a `--check` that calls GitLab breaks that promise
    and fails on a laptop with no connection.

    `glab` is replaced by a stub that fails if it is run at all, so this passes
    only because `--check` never reaches out.
    """
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name in ("glab", "gcloud"):
        stub = stubs / name
        stub.write_text(f'#!/usr/bin/env bash\necho "--check ran {name}" >&2\nexit 99\n')
        stub.chmod(0o755)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}"},
    )
    assert result.returncode == 0, f"--check failed: {result.stderr}"
    assert "--check ran" not in result.stderr, result.stderr
