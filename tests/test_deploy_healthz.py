"""Hits the deployed URL. Skipped unless TTB_DEPLOY_URL is set."""
import json
import os
import time
from pathlib import Path

import httpx
import pytest


@pytest.fixture
def deploy_url() -> str:
    url = os.environ.get("TTB_DEPLOY_URL")
    if not url:
        pytest.skip("TTB_DEPLOY_URL env var not set; skipping live deploy smoke")
    return url.rstrip("/")


def test_deployed_healthz_200(deploy_url):
    r = httpx.get(f"{deploy_url}/healthz", timeout=10.0)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"


def test_deployed_ui_shell_200(deploy_url):
    """The single-label UI shell route returns HTML."""
    r = httpx.get(f"{deploy_url}/", timeout=10.0)
    assert r.status_code == 200
    # The shell is rendered Jinja2 + island bundle reference.
    assert "<html" in r.text.lower() or "<!doctype" in r.text.lower()


def test_deployed_static_island_bundle_200(deploy_url):
    """The island bundle is served from /static/island/."""
    r = httpx.get(f"{deploy_url}/static/island/single.js", timeout=10.0)
    assert r.status_code == 200
    # JS content-type or any reasonable text/JS detection
    ct = r.headers.get("content-type", "").lower()
    assert "javascript" in ct or "text" in ct, f"unexpected content-type {ct!r}"


def test_deployed_tls_chain_valid(deploy_url):
    """The platform's own certificate; no insecure flag."""
    r = httpx.get(f"{deploy_url}/healthz", verify=True, timeout=10.0)
    assert r.status_code == 200


# --- R15/NFR-1: single-check latency, measured on the deployed product only ---
#
# The owner ruled on 2026-09-16 that speed is a property of the deployed system:
# "since we're not actually processing it on our own processor, the speed tests
# should probably only happen on the actual hugging face system." The host he
# named there has since moved to Cloud Run (decision 0025), and the ruling is
# about the deployed machine rather than about the vendor, so it carries over
# unchanged. The check lives here, behind the same TTB_DEPLOY_URL gate as its
# neighbours, and never runs on a developer machine.

_LABELS_DIR = Path(__file__).resolve().parent / "fixtures" / "labels"
_LATENCY_BUDGET_SECONDS = 5.0
_REQUIRED_SHARE_INSIDE_BUDGET = 0.95
# Well above the budget, so a slow check records a real number instead of
# raising. A request that does not finish even in this long counts as a check
# that showed no result.
_REQUEST_TIMEOUT_SECONDS = 30.0


def _form_text(value) -> str:
    """One application field as the grader's form posts it: a string, or blank.

    The manifest stores the two quantities as objects carrying the words the
    application filed plus the number read out of them. The form posts words,
    and the app parses the number itself, so only the words travel.
    """
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get("value") or "")
    return str(value)


def _submissions() -> list[tuple[str, Path, dict[str, str]]]:
    """Every test submission: its id, its front image, and its application fields.

    These are the project's own test labels with the applications filed for
    them, which is what R15 measures against — not a synthetic image, because
    reading time depends on what is actually on the label.
    """
    manifest = json.loads((_LABELS_DIR / "manifest.json").read_text())
    submissions: list[tuple[str, Path, dict[str, str]]] = []
    for entry in manifest["labels"]:
        front = _LABELS_DIR / entry["images"]["front"]
        if not front.is_file():
            continue
        application = entry.get("application") or {}
        form = {
            "beverage_type": entry["beverage_type"],
            "brand_name": _form_text(application.get("brand_name")),
            "fanciful_name": _form_text(application.get("fanciful_name")),
            "class_type": _form_text(application.get("class_type")),
            "alcohol_content": _form_text(application.get("alcohol_content")),
            "net_contents": _form_text(application.get("net_contents")),
            "applicant_name_address": _form_text(application.get("applicant_name_address")),
            "source_of_product": _form_text(application.get("source_of_product")),
            "origin": _form_text(application.get("origin")),
            "wine_appellation": _form_text(application.get("wine_appellation")),
        }
        submissions.append((entry["id"], front, form))
    return submissions


def _check_once(deploy_url: str, front: Path, form: dict[str, str]) -> tuple[int | None, float]:
    """Post one submission the way the page does, and time the round trip.

    Returns the status code and the seconds the grader waited. A timeout comes
    back as no status and the full timeout, because that is what it cost.
    """
    files = {"label": (front.name, front.read_bytes(), "image/jpeg")}
    started = time.monotonic()
    try:
        response = httpx.post(
            f"{deploy_url}/", files=files, data=form, timeout=_REQUEST_TIMEOUT_SECONDS
        )
    except httpx.TimeoutException:
        return None, _REQUEST_TIMEOUT_SECONDS
    return response.status_code, time.monotonic() - started


def test_deployed_single_check_meets_the_five_second_budget(deploy_url):
    """R15/NFR-1: 95% of single checks show results within 5 seconds.

    The requirement is a P0 (`specs/0001-label-verification/requirements.md`
    R15, `docs/PRD.md` NFR-1) and the brief is blunt about why: if results do
    not come back in about five seconds, nobody uses it. Every test submission
    is checked once in sequence, which is what R15's acceptance criterion asks
    for.

    Two things this deliberately does not do.

    It does not count the first request. The service scales to zero and the
    platform holds an idle instance no longer than 15 minutes, so the first
    check after a quiet period pays a container start and a model load. That
    number describes the start, not the product, so one warm-up submission runs
    first and its time is thrown away. The figure this test holds is a warm one,
    and anything published from it says so. The cold start has never been timed
    on the service and no figure for it belongs here until it has been
    (decision 0025).

    It does not require every check to be inside the budget. R15 is a 95th
    percentile: one check in twenty may run over. Asserting a hard maximum
    would fail a deploy for something the requirement permits.
    """
    submissions = _submissions()
    assert submissions, f"no test submissions found under {_LABELS_DIR}"

    _warm_id, warm_front, warm_form = submissions[0]
    _check_once(deploy_url, warm_front, warm_form)

    measured: list[tuple[str, int | None, float]] = []
    for label_id, front, form in submissions:
        status, elapsed = _check_once(deploy_url, front, form)
        measured.append((label_id, status, elapsed))

    no_result = [(i, s) for i, s, _ in measured if s != 200]
    assert not no_result, (
        "checks that showed no result at all (id, status; None means the "
        f"request never finished inside {_REQUEST_TIMEOUT_SECONDS:.0f}s): {no_result}"
    )

    inside = [t for _, _, t in measured if t <= _LATENCY_BUDGET_SECONDS]
    share = len(inside) / len(measured)
    slowest = sorted(measured, key=lambda row: row[2], reverse=True)[:5]
    assert share >= _REQUIRED_SHARE_INSIDE_BUDGET, (
        f"R15/NFR-1 not met: {len(inside)} of {len(measured)} checks "
        f"({share:.0%}) finished within {_LATENCY_BUDGET_SECONDS:.0f}s, "
        f"and the requirement is {_REQUIRED_SHARE_INSIDE_BUDGET:.0%}. "
        "Slowest five (id, status, seconds): "
        + ", ".join(f"{i} {s} {t:.2f}s" for i, s, t in slowest)
    )
