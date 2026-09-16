"""README.md is deliverable 1's "README with setup and run instructions".

These assertions are the README's specification, so they are written against
what this project ships rather than against its prose. Two of them are guards
rather than content checks, and those two are the reason this file is worth
having:

* every document path the README names is resolved on disk, so a reorganisation
  that leaves a dead link fails here instead of in front of a reviewer;
* the accuracy section may not carry a number, because the project publishes
  only figures a run on this machine produced and no such run has happened yet.
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


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def _section(content: str, heading: str) -> str:
    """The body under ``heading``, up to the next heading of the same level."""
    level = heading.split(" ", 1)[0]
    start = content.index(heading)
    rest = content[start + len(heading):]
    nxt = re.search(rf"^{re.escape(level)} ", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def test_readme_declares_the_space_card() -> None:
    """The deploy host reads its configuration from this block (decision 0023).

    ``app_port`` is not optional: the platform defaults to 7860 and this app
    listens on 8000, so a missing line serves a reviewer a blank page.
    ``suggested_hardware`` is the documented key name — ``hardware`` is not one.
    """
    content = _readme()
    assert content.startswith("---\n"), "README must open with the Space card block"
    card = content.split("---\n", 2)[1]
    for marker in ("sdk: docker", "app_port: 8000", "suggested_hardware: cpu-basic"):
        assert marker in card, f"Space card missing {marker!r}"


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

    No reading-accuracy run has happened yet, so the section holds a marked hole.
    A percentage appearing here before that run is an estimate, and an estimate
    presented as a measurement is the one thing this section may not contain.
    """
    accuracy = _section(_readme(), "## Reading accuracy")
    assert "%" not in accuracy, "accuracy section carries a figure no run produced"
    assert "not published" in accuracy.lower()


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


def test_readme_records_the_latency_requirement_as_unverified() -> None:
    """A P0 with no measurement has to be stated, not omitted.

    R15/NFR-1 promises 95 percent of single checks inside five seconds and no
    run has confirmed it. A README that simply stays quiet about it reads
    exactly like one whose product met it, so the silence is the failure this
    guard catches. The section also names the test that takes the number, so
    whoever stands the Space up knows what to run.
    """
    deployed = _section(_readme(), "## Deployed URL")
    assert "not verified" in deployed.lower(), (
        "Deployed URL section no longer records R15/NFR-1 as unverified"
    )
    assert "tests/test_deploy_healthz.py" in deployed, (
        "Deployed URL section does not name the test that measures it"
    )
