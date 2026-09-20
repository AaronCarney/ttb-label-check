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
    rest = content[start + len(heading) :]
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
    # A count, not a percentage, and not a fixed one: the number of test
    # submissions moves with the corpus, and pinning the guard to one of them
    # made it fail on a run of a different size rather than on a README that
    # had gone quiet.
    assert re.search(r"\b\d+ of \d+ checks\b", deployed), (
        "Deployed URL section publishes no measured share of checks inside the budget"
    )
    assert "not met" in deployed.lower(), (
        "Deployed URL section does not say the five-second requirement is missed"
    )
    assert "tests/test_deploy_healthz.py" in deployed, (
        "Deployed URL section does not name the test that measures it"
    )


def test_readme_says_there_is_no_held_out_set() -> None:
    """The accuracy figures were measured on the labels the reader was tuned on.

    Every heuristic in `app/vision/local.py` — the box-merge ratios, the
    sideways-text gate, the field regexes — was tuned against this same
    30-label corpus, and the table above is scored on it. That makes the
    figures in-sample: an upper bound on what the reader does with a label it
    has never seen, not an estimate of it.

    Publishing them without that reads as a measurement of general
    performance, which is the claim this project cannot support and does not
    need to make. It matters most for `warning_present`, whose 30 of 30 is
    what licenses the one rule in any pack allowed to reject a label because
    the reader found nothing — see `tests/rules/test_rule_pack_citations.py`.
    """
    accuracy = _section(_readme(), "## Reading accuracy")
    assert "held-out" in accuracy, "accuracy section does not say there is no held-out set"
    assert "in-sample" in accuracy, "accuracy section does not say the figures are in-sample"


def test_readme_states_the_upload_limits_the_service_enforces() -> None:
    """A reviewer who hits a limit has to be able to find it written down.

    The numbers come from `app/api/limits.py`, formatted as the refusal
    messages format them, so moving a limit without moving the README fails
    here rather than in front of someone whose upload was refused for a
    reason the documentation does not mention.
    """
    from app.api import limits

    content = _readme()
    expected = {
        "request cap": limits._mib(limits.MAX_REQUEST_BYTES),
        "per-image cap": limits._mib(limits.MAX_UPLOAD_BYTES),
        "files per batch": str(limits.MAX_BATCH_FILES),
        "pixel ceiling": f"{limits.MAX_IMAGE_PIXELS:,}",
    }
    missing = [f"{name} ({value})" for name, value in expected.items() if value not in content]
    assert not missing, f"README does not state: {missing}"


def test_both_graded_documents_state_the_effective_batch_limit() -> None:
    """ "100 images per batch" is only reachable for small images, and a reader
    who is told the count without the byte cap cannot work out why a hundred
    ordinary labels were refused.

    The figures are derived here from `app/api/limits.py` rather than typed, so
    moving a cap fails this test instead of quietly leaving both documents
    advertising a batch size the request cap will not carry. The three anchors
    are the ones a reviewer meets: the average that makes a full batch fit, the
    count at the per-image cap, and the count at the largest label this
    project's own corpus holds.
    """
    from app.api import limits

    largest_corpus_label_bytes = max(
        path.stat().st_size for path in (ROOT / "tests/fixtures/labels").rglob("*.jpg")
    )
    expected = {
        "the average a full batch needs": limits._mib(limits.BATCH_AVERAGE_BYTES),
        "the count at the per-image cap": str(limits.files_that_fit(limits.MAX_UPLOAD_BYTES)),
        "the count at the largest corpus label": str(
            limits.files_that_fit(largest_corpus_label_bytes)
        ),
    }

    for document in (README, ROOT / "docs/approach.md"):
        content = document.read_text(encoding="utf-8")
        paragraph = next(
            (block for block in content.split("\n\n") if "average under" in block),
            "",
        )
        assert paragraph, f"{document.name} does not state when 100 per batch is reachable"
        missing = [
            f"{name} ({value})" for name, value in expected.items() if value not in paragraph
        ]
        assert not missing, f"{document.name} does not state: {missing}"


def test_readme_names_the_photo_the_app_refuses_to_read() -> None:
    """A photo turned away for quality gets no compliance check at all.

    `app/vision/quality.py` refuses a reading before any rule runs (step 2 of
    `app/services/evaluator.py`), so the envelope comes back `needs_review`
    with a legibility reason code and no field findings. The refusal itself is
    not hidden - the reason code reaches the audit trail as a synthetic
    per-rule entry. What a reviewer cannot see from the envelope is that the
    line was drawn by two thresholds this project picked, or where they sit.
    "Needs a better photo" reads as a statement about the photograph; it is
    also a statement about the limit of what this app will judge.

    The numbers are read from the module, so moving a threshold without moving
    the README fails here rather than in front of someone whose label was
    refused.
    """
    from app.vision import quality

    limitations = _section(_readme(), "## Limitations")
    expected = {
        "low-detail threshold": str(quality.LOW_RES_VARIANCE_MIN),
        "motion-blur threshold": str(quality.MOTION_BLUR_HIGHFREQ_MIN),
    }
    missing = [f"{name} ({value})" for name, value in expected.items() if value not in limitations]
    assert not missing, f"Limitations does not state: {missing}"
    assert "no compliance rule runs" in limitations, (
        "Limitations does not say that a refused photo is checked against nothing"
    )


def test_readme_names_the_re_read_that_can_decline_to_fire() -> None:
    """The one gate here that really does leave no trace.

    The rotated re-read that finds a sideways government warning runs only
    when three things are true at once (`app/vision/local.py`): no heading was
    found upright, the box shapes look sideways, and the sideways strips read
    like the warning. When either of the last two says no, the label is read
    upright only and reported as carrying no warning - and nothing in the
    envelope records that a re-read was considered and declined. Since a
    missing warning became a rejection, that silence decides labels.
    """
    limitations = _section(_readme(), "## Limitations")
    assert "declined" in limitations or "decline" in limitations, (
        "Limitations does not say the rotated re-read can decline to fire silently"
    )
