"""Hits the deployed URL. Skipped unless TTB_DEPLOY_URL is set."""

import json
import os
import statistics
import time
from datetime import UTC, datetime
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
    r = httpx.get(f"{deploy_url}/api/health", timeout=10.0)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"


def test_deployed_ui_shell_200(deploy_url):
    """The check page returns HTML."""
    r = httpx.get(f"{deploy_url}/", timeout=10.0)
    assert r.status_code == 200
    # The shell is rendered Jinja2 + island bundle reference.
    assert "<html" in r.text.lower() or "<!doctype" in r.text.lower()


def test_deployed_static_island_bundle_200(deploy_url):
    """The island bundle the results page loads is served from /static/island/."""
    r = httpx.get(f"{deploy_url}/static/island/app.js", timeout=10.0)
    assert r.status_code == 200
    # JS content-type or any reasonable text/JS detection
    ct = r.headers.get("content-type", "").lower()
    assert "javascript" in ct or "text" in ct, f"unexpected content-type {ct!r}"


def test_deployed_tls_chain_valid(deploy_url):
    """The platform's own certificate; no insecure flag."""
    r = httpx.get(f"{deploy_url}/api/health", verify=True, timeout=10.0)
    assert r.status_code == 200


# --- R15/NFR-1: single-check latency, measured on the deployed product only ---
#
# The owner ruled that speed is a property of the deployed system:
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
    """One application field as the reviewer's form posts it: a string, or blank.

    The manifest stores the two quantities as objects carrying the words the
    application filed plus the number read out of them. The form posts words,
    and the app parses the number itself, so only the words travel.
    """
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get("value") or "")
    return str(value)


def _submissions() -> list[tuple[str, list[Path], dict[str, str]]]:
    """Every test submission: its id, its images, and its application fields.

    These are the project's own test labels with the applications filed for
    them, which is what R15 measures against — not a synthetic image, because
    reading time depends on what is actually on the label.

    Every face the manifest lists travels, because that is what a reviewer
    checking one label sends, and 34 of the 38 test labels have a back.
    Measuring a front-only submission would be measuring something no reviewer
    posts, and the back is not free —
    the faces are read one after another (`app/vision/local.py`), so a second
    face costs roughly a second read.
    """
    manifest = json.loads((_LABELS_DIR / "manifest.json").read_text())
    submissions: list[tuple[str, list[Path], dict[str, str]]] = []
    for entry in manifest["labels"]:
        front = _LABELS_DIR / entry["images"]["front"]
        if not front.is_file():
            continue
        faces = [front]
        back_name = (entry.get("images") or {}).get("back")
        if back_name:
            back = _LABELS_DIR / back_name
            if back.is_file():
                faces.append(back)
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
        submissions.append((entry["id"], faces, form))
    return submissions


# --- Recording what came back, not only how long it took ---
#
# This harness used to keep a status code and a wall clock and throw
# both away on a pass. Two checks that look identical to it are not the same
# thing at all: one that ran five seconds and returned seven fields, and one
# that ran five seconds, was stopped by the evaluation guard, and returned
# none. Four consecutive runs against production yielded the same two facts and
# no way to tell those apart. Every run now leaves a file behind saying what
# each check answered.

# The evaluation guard stopping a check before it finished
# (`app/services/evaluator.py`). Such a check returns HTTP 200 and an incomplete
# answer, so nothing but the audit trail distinguishes it from a slow one.
_STOPPED_EARLY_CODE = "ENGINE.SLA.TIMEOUT"

# Where a run leaves its rows. One file per run, named for when it ran, so two
# runs can be compared instead of the second overwriting the first.
_RECORD_DIR = Path(os.environ.get("TTB_LATENCY_RECORD_DIR", "artifacts/deploy-latency"))


def _row_from_result(
    label_id: str, status: int | None, wall_seconds: float, envelope: dict | None, faces: int
) -> dict:
    """One check, as the record keeps it.

    `faces` is how many images the submission carried, because a one-faced
    label and a two-faced one are not the same measurement and a run mixing
    both cannot be read without it.
    """
    row: dict = {
        "label_id": label_id,
        "status": status,
        "wall_seconds": wall_seconds,
        "faces": faces,
        "disposition": None,
        "field_count": None,
        "total_duration_ms": None,
        "vision_duration_ms": None,
        "cache_hit": None,
        "stopped_early": None,
        "trace": None,
    }
    if envelope is None:
        return row
    metrics = envelope.get("metrics") or {}
    trace = [
        entry.get("rule_id")
        for entry in (envelope.get("audit_trail") or {}).get("per_rule_trace") or []
    ]
    row.update(
        disposition=envelope.get("disposition"),
        field_count=len(envelope.get("fields") or []),
        total_duration_ms=metrics.get("total_duration_ms"),
        vision_duration_ms=metrics.get("vision_duration_ms"),
        cache_hit=metrics.get("cache_hit"),
        stopped_early=_STOPPED_EARLY_CODE in trace,
        trace=trace,
    )
    return row


def _summarise(rows: list[dict]) -> dict:
    """The figures a run is quoted for, worked out once and written down."""
    walls = [row["wall_seconds"] for row in rows]
    # Only a check that showed a result can be inside the budget. A submission
    # the service refused comes back in well under a second, and counting it
    # would turn a busy service into a fast one.
    inside = [
        row["wall_seconds"]
        for row in rows
        if row["status"] == 200 and row["wall_seconds"] <= _LATENCY_BUDGET_SECONDS
    ]
    return {
        "checked": len(rows),
        "two_faced": sum(1 for row in rows if (row.get("faces") or 1) > 1),
        "inside_budget": len(inside),
        "share_inside_budget": len(inside) / len(rows) if rows else 0.0,
        "budget_seconds": _LATENCY_BUDGET_SECONDS,
        "median_wall_seconds": statistics.median(walls) if walls else None,
        "max_wall_seconds": max(walls) if walls else None,
        "stopped_early": sum(1 for row in rows if row.get("stopped_early")),
        "cache_hits": sum(1 for row in rows if row.get("cache_hit")),
        "no_result": sum(1 for row in rows if row["status"] != 200),
    }


def _host(deploy_url: str) -> dict | None:
    """The processor the service reports, or None if it did not answer.

    Read before and after the run: the service runs one instance, but one that
    is replaced mid-run can land on a different processor, and the two readings
    show whether that happened.
    """
    try:
        response = httpx.get(f"{deploy_url}/api/health", timeout=_REQUEST_TIMEOUT_SECONDS)
        return response.json().get("host")
    except (httpx.HTTPError, ValueError):
        return None


def _write_record(
    deploy_url: str, rows: list[dict], hosts: tuple[dict | None, dict | None] = (None, None)
) -> Path:
    _RECORD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = _RECORD_DIR / f"{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "url": deploy_url,
                "measured_at": datetime.now(UTC).isoformat(),
                "host_before": hosts[0],
                "host_after": hosts[1],
                "summary": _summarise(rows),
                "rows": rows,
            },
            indent=2,
        )
    )
    return path


def _check_once(
    deploy_url: str,
    faces: list[Path],
    form: dict[str, str],
    transport: httpx.BaseTransport | None = None,
) -> tuple[int | None, float, dict | None]:
    """Post one submission the way the page does, and time it to the result shown.

    Every face goes in the repeatable `labels` field with `one_label` set, which
    is what the page posts when a reviewer ticks *These images are all faces of
    one label* (`app/api/ui/submit.py`). The typed application travels as form
    fields, which apply because the submission is one label.

    `POST /` answers 303 to the batch's page, and the result reaches the page as
    the `label-result` event on `/batches/{id}/stream` (`app/batch/worker.py`),
    so that event's arrival is when the reviewer is shown the result. The clock
    starts before the upload, because uploading is part of the wait.

    Returns 200 and the envelope when a result arrived, the status `POST /`
    answered when it refused, or no status when nothing arrived inside the
    timeout — which comes back as the full timeout, because that is what it cost.
    `transport` stands in for the network in `tests/test_deploy_latency_record.py`.
    """
    files = [("labels", (face.name, face.read_bytes(), "image/jpeg")) for face in faces]
    started = time.monotonic()
    try:
        with httpx.Client(
            base_url=deploy_url, timeout=_REQUEST_TIMEOUT_SECONDS, transport=transport
        ) as client:
            response = client.post(
                "/", files=files, data={**form, "one_label": "1"}, follow_redirects=False
            )
            if response.status_code != 303:
                return response.status_code, time.monotonic() - started, None
            batch_id = response.headers["location"].rstrip("/").rsplit("/", 1)[-1]
            # Read on to `stream-end` after the result, untimed: the service
            # takes one batch at a time and answers 409 to the next submission
            # until this one has finished.
            shown: tuple[float, dict | None] | None = None
            with client.stream("GET", f"/batches/{batch_id}/stream") as stream:
                event = ""
                for line in stream.iter_lines():
                    if line.startswith("event:"):
                        event = line.split(":", 1)[1].strip()
                        if event == "stream-end":
                            break
                    elif line.startswith("data:") and event == "label-result" and shown is None:
                        elapsed = time.monotonic() - started
                        payload = json.loads(line.split(":", 1)[1].strip())
                        shown = (elapsed, payload.get("envelope"))
    except httpx.TimeoutException:
        return None, _REQUEST_TIMEOUT_SECONDS, None
    if shown is None:
        return None, time.monotonic() - started, None
    return 200, shown[0], shown[1]


def test_deployed_single_check_meets_the_five_second_budget(deploy_url):
    """R15/NFR-1: 95% of single checks show results within 5 seconds.

    The requirement is a P0 (`specs/0001-label-verification/requirements.md`
    R15, `docs/PRD.md` NFR-1) and the brief is blunt about why: if results do
    not come back in about five seconds, nobody uses it. Every test submission
    is checked once in sequence, which is what R15's acceptance criterion asks
    for.

    Three things this deliberately does.

    It warms the service and then leaves that submission out of the measured
    set. The service scales to zero and the platform holds an idle instance no
    longer than 15 minutes, so the first check after a quiet period pays a
    container start and a model load, and that number describes the start
    rather than the product. The warm-up submission also used to be
    measured, as sample 0 — and by then the service had it cached, so a
    guaranteed cache hit counted as a check, worth 2.6 points of the reported
    share on 38 samples. A cached answer is not a check; the figure this test
    holds is a warm one, and anything published from it says so. The cold start
    has never been timed on the service and no figure for it belongs here until
    it has been (decision 0025).

    It does not require every check to be inside the budget. R15 is a 95th
    percentile: one check in twenty may run over. Asserting a hard maximum
    would fail a deploy for something the requirement permits.

    It writes every row to a file, and fails on a check the evaluation guard
    stopped. A stopped check returns HTTP 200 with an incomplete answer, so a
    harness that keeps only the status and the clock cannot see it at all —
    which is how a defect that blanked one check in twelve survived four runs
    against production.
    """
    submissions = _submissions()
    assert len(submissions) > 1, f"need more than one test submission under {_LABELS_DIR}"

    # The warm-up, thrown away: it pays for the container start and the model
    # load, and it leaves the service holding this submission's answer.
    _warm_id, warm_faces, warm_form = submissions[0]
    _check_once(deploy_url, warm_faces, warm_form)
    host_before = _host(deploy_url)

    measured: list[dict] = []
    for label_id, faces, form in submissions[1:]:
        status, elapsed, envelope = _check_once(deploy_url, faces, form)
        measured.append(_row_from_result(label_id, status, elapsed, envelope, len(faces)))

    record = _write_record(deploy_url, measured, (host_before, _host(deploy_url)))
    summary = _summarise(measured)
    slowest = sorted(measured, key=lambda row: row["wall_seconds"], reverse=True)[:5]
    where = f"Rows for this run are in {record}."

    no_result = [(row["label_id"], row["status"]) for row in measured if row["status"] != 200]
    assert not no_result, (
        "checks that showed no result at all (id, status; None means the "
        f"request never finished inside {_REQUEST_TIMEOUT_SECONDS:.0f}s): "
        f"{no_result}. {where}"
    )

    # A check the guard stopped comes back incomplete. Whether it was inside the
    # budget is beside the point: it did not answer the question it was asked.
    stopped = [
        (row["label_id"], row["wall_seconds"], row["field_count"])
        for row in measured
        if row["stopped_early"]
    ]
    assert not stopped, (
        "checks the evaluation guard stopped before they finished, so their "
        "results are incomplete (id, seconds, fields returned): "
        + ", ".join(f"{i} {t:.2f}s {n}" for i, t, n in stopped)
        + f". {where}"
    )

    # A cached answer is the service handing back an earlier check. It costs
    # almost nothing and measures nothing, so its presence means the sample is
    # not what it claims to be.
    cached = [row["label_id"] for row in measured if row["cache_hit"]]
    assert not cached, f"checks answered out of the cache rather than measured: {cached}. {where}"

    assert summary["share_inside_budget"] >= _REQUIRED_SHARE_INSIDE_BUDGET, (
        f"R15/NFR-1 not met: {summary['inside_budget']} of {summary['checked']} "
        f"checks ({summary['share_inside_budget']:.0%}) finished within "
        f"{_LATENCY_BUDGET_SECONDS:.0f}s, and the requirement is "
        f"{_REQUIRED_SHARE_INSIDE_BUDGET:.0%}. Slowest five "
        "(id, seconds, fields, read ms): "
        + ", ".join(
            f"{row['label_id']} {row['wall_seconds']:.2f}s {row['field_count']} "
            f"{row['vision_duration_ms']}ms"
            for row in slowest
        )
        + f". {where}"
    )
