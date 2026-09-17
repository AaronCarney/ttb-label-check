"""A deploy that ships code must not change who can reach the service.

On 2026-09-17 the live service was open to the public (`allUsers` held
`roles/run.invoker`) and five committed bug fixes were waiting to go out.
Running the deploy as written would have passed `--no-allow-unauthenticated`
and closed the service to everyone, because the script's default fails closed
and a code deploy carried that decision in with it. Opening a service is the
owner's call every time; leaving it as he set it is not a decision at all, and
a bug-fix deploy should not make one.

These run the real script against a stand-in `gcloud` that records its
arguments, so what is asserted is what the script would actually send, not what
its text looks like.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path("scripts/deploy.sh")


def _run_deploy(tmp_path: Path, env: dict[str, str]) -> list[list[str]]:
    """Run the deploy with a fake gcloud, and return each call's argv."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.txt"
    fake = bin_dir / "gcloud"
    fake.write_text(f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "{calls}"\nexit 0\n')
    fake.chmod(0o755)

    child = dict(os.environ)
    child["PATH"] = f"{bin_dir}:{child['PATH']}"
    child["TTB_GCP_PROJECT"] = "fake-project"
    # These tests are about the access flag, not about the pipeline gate that
    # sits above it, and the gate would otherwise ask GitLab for a verdict on
    # whatever commit the suite happens to be running at. The gate has its own
    # tests in `tests/test_deploy_pipeline_gate.py`.
    child["TTB_SKIP_PIPELINE_CHECK"] = "1"
    child.pop("TTB_PUBLIC", None)
    child.pop("TTB_ACCESS", None)
    child.update(env)

    done = subprocess.run(
        ["bash", str(SCRIPT)], env=child, capture_output=True, text=True, timeout=300
    )
    assert done.returncode == 0, done.stderr
    if not calls.exists():
        return []
    return [shlex.split(line) for line in calls.read_text().splitlines() if line.strip()]


@pytest.fixture
def deploy_call():
    def _first_deploy(calls: list[list[str]]) -> list[str]:
        for argv in calls:
            if argv[:2] == ["run", "deploy"]:
                return argv
        raise AssertionError(f"no 'gcloud run deploy' call was made; got {calls}")

    return _first_deploy


def test_keep_passes_no_access_flag_at_all(tmp_path: Path, deploy_call) -> None:
    """gcloud only touches the IAM policy when the flag is set to something --
    `if allow_unauthenticated is not None` in serverless_operations.py. Omitting
    it is therefore the only way to deploy and leave the policy alone."""
    calls = _run_deploy(tmp_path, {"TTB_ACCESS": "keep"})
    argv = deploy_call(calls)
    assert "--allow-unauthenticated" not in argv
    assert "--no-allow-unauthenticated" not in argv
    assert "" not in argv, (
        "an empty string was passed as an argument; gcloud reads it as a "
        "positional and the deploy fails"
    )


def test_keep_makes_no_iam_call_of_its_own(tmp_path: Path) -> None:
    """The invoker grant at the end of the script is also an IAM write. Under
    keep, the deploy touches access from neither end."""
    calls = _run_deploy(tmp_path, {"TTB_ACCESS": "keep"})
    assert not [argv for argv in calls if "add-iam-policy-binding" in argv], (
        "TTB_ACCESS=keep still wrote an IAM binding"
    )


def test_default_still_fails_closed(tmp_path: Path, deploy_call) -> None:
    """With nothing set, the script must go on refusing anonymous callers. The
    keep mode is an opt-in, not a loosening of the default."""
    calls = _run_deploy(tmp_path, {})
    assert "--no-allow-unauthenticated" in deploy_call(calls)


def test_public_still_opens_the_service(tmp_path: Path, deploy_call) -> None:
    calls = _run_deploy(tmp_path, {"TTB_PUBLIC": "1"})
    assert "--allow-unauthenticated" in deploy_call(calls)


def test_public_wins_over_keep(tmp_path: Path, deploy_call) -> None:
    """Both set is a contradiction. The explicit instruction to open wins, and
    the script documents that it does, so the outcome is never a surprise."""
    calls = _run_deploy(tmp_path, {"TTB_PUBLIC": "1", "TTB_ACCESS": "keep"})
    assert "--allow-unauthenticated" in deploy_call(calls)
