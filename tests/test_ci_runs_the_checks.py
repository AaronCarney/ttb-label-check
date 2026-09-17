"""The pipeline runs what a reviewer is told it runs.

The 742-and-growing suite ran only when a person typed the command, which is
how seven browser tests failed unnoticed for days. A pipeline fixes that only
if it actually runs every check, and only if a failing job actually fails the
pipeline — a job carrying `allow_failure: true` is the same defect as the
`xfail(strict=False)` tests in P3-1, a check that is counted and cannot fail.

This test reads `.gitlab-ci.yml` rather than trusting the README's account of
it. What it cannot check is that the pipeline ran: that is the pipeline's job,
and the commit that adds this file is pushed and watched.
"""

from pathlib import Path

import pytest
import yaml

CI_FILE = Path(".gitlab-ci.yml")

# Origin is GitLab, so this is the file that runs. Each command is the one the
# README's "Linting, formatting and type checking" section tells a reader to
# run, plus the suite itself.
REQUIRED_COMMANDS = (
    "ruff check",
    "ruff format --check",
    "mypy",
    "pytest",
    # A coverage report produced only on a developer's machine is a number
    # nobody sees again.
    "--cov",
)

# GitLab's own reserved top-level keys, which are configuration rather than
# jobs. Anything else at the top level is a job.
_NOT_JOBS = {
    "default",
    "include",
    "stages",
    "variables",
    "workflow",
    "image",
    "services",
    "before_script",
    "after_script",
    "cache",
}


def _config() -> dict:
    assert CI_FILE.is_file(), f"{CI_FILE} does not exist, so a push runs nothing"
    loaded = yaml.safe_load(CI_FILE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{CI_FILE} is not a mapping"
    return loaded


def _jobs(config: dict) -> dict[str, dict]:
    return {
        name: body
        for name, body in config.items()
        if name not in _NOT_JOBS and not name.startswith(".") and isinstance(body, dict)
    }


def _all_script_lines(config: dict) -> list[str]:
    lines: list[str] = []
    for body in _jobs(config).values():
        for key in ("before_script", "script", "after_script"):
            value = body.get(key) or []
            if isinstance(value, str):
                lines.append(value)
            else:
                lines.extend(str(line) for line in value)
    return lines


def test_the_pipeline_defines_at_least_one_job():
    jobs = _jobs(_config())
    assert jobs, "the pipeline defines no jobs, so a push runs nothing"


@pytest.mark.parametrize("command", REQUIRED_COMMANDS)
def test_the_pipeline_runs_each_check(command):
    lines = _all_script_lines(_config())
    assert any(command in line for line in lines), (
        f"no job in {CI_FILE} runs `{command}`; a check nothing runs is not a check"
    )


def test_no_job_is_allowed_to_fail():
    offenders = [
        name for name, body in _jobs(_config()).items() if body.get("allow_failure") is True
    ]
    assert not offenders, (
        f"{offenders} carry `allow_failure: true`, so the pipeline stays green when they fail"
    )


def test_a_job_tells_gitlab_how_to_read_the_coverage_number():
    """The report has to reach the pipeline page, not just the job log.

    `coverage:` is the regex GitLab runs over a job's output to pull the
    percentage out; without it the number is buried in a log nobody opens, which
    is the same as not measuring it.
    """
    jobs = _jobs(_config())
    assert any("coverage" in body for body in jobs.values()), (
        "no job carries a `coverage:` regex, so the measured percentage never "
        "reaches the pipeline page"
    )
