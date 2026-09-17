"""README.md is deliverable 1's "README with setup and run instructions".

These assertions are the README's specification, so they are written against
what this project ships rather than against its prose. Two of them are guards
rather than content checks, and those two are the reason this file is worth
having:

* every document path the README names is resolved on disk, so a reorganisation
  that leaves a dead link fails here instead of in front of a reviewer;
* the accuracy section publishes only what a run on this machine measured, in
  the form decision 0027 settled: counts rather than percentages, every check
  named, and the corpus the figures came from stated.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
README = ROOT / "README.md"

# The seven label elements the brief lists, and which the coverage table answers
# for one by one (`specs/0001-label-verification/PRD.md`, "About TTB Label
# Requirements").
BRIEF_ELEMENTS = (
    "Brand name",
    "Class/type designation",
    "Alcohol content",
    "Net contents",
    "Name and address",
    "Country of origin",
    "Government Health Warning",
)


# The nine checks ``eval/read_accuracy.py`` scores, named as it names them, so a
# reader can match a figure in the README to a line of the run's own output.
ACCURACY_CHECKS = (
    "brand",
    "class_type",
    "abv",
    "net_contents",
    "name_address",
    "origin",
    "warning_present",
    "warning_exact",
    "warning_heading_caps",
)


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def _section(content: str, heading: str) -> str:
    """The body under ``heading``, up to the next heading of the same level."""
    level = heading.split(" ", 1)[0]
    start = content.index(heading)
    rest = content[start + len(heading):]
    nxt = re.search(rf"^{re.escape(level)} ", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def test_readme_deploy_section_names_the_host_and_the_command() -> None:
    """A reviewer has to be able to stand this up from the README alone.

    The host reads no configuration out of this file — Cloud Run takes its
    settings from the arguments ``scripts/deploy.sh`` passes it (decision 0025)
    — so what the README owes is the host, the command, and the one variable the
    command refuses to guess at. The port those settings share with the
    container is held together in ``tests/test_dockerfile_lint.py``.
    """
    deployed = _section(_readme(), "## Deployed URL")
    for marker in ("Cloud Run", "scripts/deploy.sh --check", "TTB_GCP_PROJECT"):
        assert marker in deployed, f"Deployed URL section missing {marker!r}"


def test_readme_getting_started_runs_the_app() -> None:
    """Deliverable 1 asks for setup and run instructions; these are the commands."""
    content = _readme()
    assert "## Getting started" in content
    setup = _section(content, "## Getting started")
    for command in ("uv sync", "uv run task demo"):
        assert command in setup, f"Getting started missing {command!r}"


def test_readme_says_the_default_reader_needs_no_key() -> None:
    """Guards the promise decision 0004 makes about a clone.

    ``VISION_MODE`` defaults to ``local`` (``app/config.py``), which reads labels
    with an OCR engine inside the process. A README that presents an API key as
    a setup step would describe a product this one is not.
    """
    setup = _section(_readme(), "## Getting started")
    assert "no API key" in setup or "no key" in setup


def test_readme_links_only_documents_that_exist() -> None:
    """Every repository document the README names resolves on disk."""
    named = set(re.findall(r"[A-Za-z0-9_./-]+\.md", _readme()))
    missing = sorted(p for p in named if not (ROOT / p).exists())
    assert not missing, f"README names documents that are not in the tree: {missing}"


def test_readme_names_the_documents_a_reviewer_needs() -> None:
    """Requirements, mechanism and settled forks each have one home."""
    content = _readme()
    for ref in ("docs/PRD.md", "ARCHITECTURE.md", "docs/decisions.md"):
        assert ref in content, f"README missing pointer to {ref}"


def test_readme_carries_a_deployed_url_section() -> None:
    """Deliverable 2 is a URL Treasury can access and test."""
    assert "## Deployed URL" in _readme()


def test_readme_publishes_no_unmeasured_accuracy() -> None:
    """The README states only what a run on this machine measured.

    The run has happened, so the section carries its figures instead of the
    marked hole it held before (decision 0027). The failure guarded against is
    the same one: a number in front of a reviewer that no run produced. A
    percentage is that number here — none was measured, thirty labels is too
    small a denominator to express as one, and the denominator differs between
    checks — so the form is counts, every check named, and the corpus stated.
    """
    accuracy = _section(_readme(), "## Reading accuracy")
    assert "%" not in accuracy, "accuracy section carries a figure no run produced"
    for check in ACCURACY_CHECKS:
        assert f"`{check}`" in accuracy, f"accuracy section does not report {check!r}"
    for corpus in ("30", "56", "tests/fixtures/labels", "local"):
        assert corpus in accuracy, f"accuracy section does not state {corpus!r}"


def test_readme_coverage_table_answers_every_brief_element() -> None:
    """The brief-coverage table accounts for all seven label elements."""
    coverage = _section(_readme(), "## What the brief asked for")
    missing = [e for e in BRIEF_ELEMENTS if e not in coverage]
    assert not missing, f"coverage table does not answer: {missing}"


def test_readme_coverage_table_answers_both_deliverables() -> None:
    """Deliverable 1 is the repository and its README; deliverable 2 is the URL."""
    coverage = _section(_readme(), "## What the brief asked for")
    for deliverable in ("Source code repository", "Deployed application URL"):
        assert deliverable in coverage, f"coverage table missing {deliverable!r}"


def test_readme_records_the_measured_latency_and_the_shortfall() -> None:
    """A P0 the product misses has to be stated, not omitted.

    R15/NFR-1 promises 95 percent of single checks inside five seconds. The
    service is up and the measurement has been taken, and it comes in under
    that. A README that stays quiet about it, or that publishes the share
    without the requirement beside it, reads exactly like one whose product met
    the promise — that silence is the failure this guard catches. It replaces an
    earlier guard that required the section to call the figure unverified, which
    was right for as long as no run had produced one. The section also still
    names the test that takes the number, so a reader can repeat it.
    """
    deployed = _section(_readme(), "## Deployed URL")
    assert "95%" in deployed or "95 percent" in deployed, (
        "Deployed URL section does not state the share R15/NFR-1 requires"
    )
    assert "of 38" in deployed, (
        "Deployed URL section publishes no measured share of checks inside the budget"
    )
    assert "not met" in deployed.lower(), (
        "Deployed URL section does not say the five-second requirement is missed"
    )
    assert "tests/test_deploy_healthz.py" in deployed, (
        "Deployed URL section does not name the test that measures it"
    )
