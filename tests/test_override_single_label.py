"""A reviewer can overrule a label whose batch the service is no longer holding.

The override endpoint used to search in-flight batches and nothing else, and a
single-label check kept no result at all, so every override against one
answered 404. Every check is a batch now (`docs/decisions.md#0045`), but the
service holds one at a time and drops the finished one the moment the next
starts (`docs/decisions.md#0041`) — so the same 404 is one upload away unless
the result store is what the override reads. These drive the real routes end to
end: check a label, start a second check so the first batch is dropped,
override, and read the record back.
"""

from __future__ import annotations

import time
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.ui._submission import _get_upload_evaluator
from app.api.ui.images import UploadImageStore, _get_image_store
from app.api.ui.results import SingleResultStore, _get_result_store
from app.main import create_app
from tests._fakes.evaluator import FakeEvaluator
from tests.conftest import _stub_disposition_envelope

_REASON_CODE = "BRAND.NAME.MISMATCH"


def _png_1x1() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (1, 1), color=(0, 0, 0)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def stores(tmp_path: Path):
    """The real app with both stores under the test's own directory.

    Two envelopes, because every test here checks a second label to make the
    service drop the first one's batch. Entered as a context manager: the check
    runs as a background task on the app's own loop.
    """
    envelope = _stub_disposition_envelope(7, disposition="pass")
    later = _stub_disposition_envelope(8, disposition="pass")
    results = SingleResultStore(tmp_path / "results")
    app = create_app()
    # One evaluator for the whole client, not one per request: a fresh
    # FakeEvaluator restarts its plan, so the second check would answer with
    # the first check's envelope and the two labels would share an evaluation
    # id — which is the very thing these tests distinguish.
    evaluator = FakeEvaluator([(0.0, envelope), (0.0, later)])
    app.dependency_overrides[_get_upload_evaluator] = lambda: evaluator
    app.dependency_overrides[_get_image_store] = lambda: UploadImageStore(tmp_path / "images")
    app.dependency_overrides[_get_result_store] = lambda: results
    with TestClient(app) as client:
        yield client, results, envelope.evaluation_id


def _check_one_label(client: TestClient, name: str = "label.png") -> str:
    """Check one label and wait for it; returns the batch it was checked in."""
    response = client.post(
        "/",
        files={"labels": (name, _png_1x1(), "image/png")},
        data={"beverage_type": "distilled_spirits"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    batch_id = response.headers["location"].removeprefix("/batch/")
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        items = client.get(f"/batches/{batch_id}").json()["items"]
        if items and all(item["state"] in ("ready", "failed") for item in items):
            break
        time.sleep(0.02)
    return batch_id


def test_single_label_override_is_recorded(stores) -> None:
    client, results, evaluation_id = stores

    first_batch = _check_one_label(client)
    # A second check drops the first one's batch, so the label being overridden
    # below is in no batch the service is holding — the case that used to 404.
    _check_one_label(client, "another.png")
    assert first_batch not in client.app.state.batches

    response = client.post(
        f"/labels/{evaluation_id}/overrides",
        json={
            "field_name": None,
            "applied_disposition": "fail",
            "reason_code": _REASON_CODE,
            "justification_text": "Brand on the label is not the one filed.",
        },
    )
    assert response.status_code == 200, response.text
    entry = response.json()
    assert entry["applied_disposition"] == "fail"
    assert entry["reason_code"] == _REASON_CODE
    assert entry["original_disposition"] == "pass"

    # The record itself carries it, not just the reply.
    kept = results.get(evaluation_id)
    assert kept is not None
    assert len(kept.audit_trail.overrides) == 1
    assert kept.audit_trail.overrides[0].reason_code == _REASON_CODE


def test_two_overrides_on_one_label_both_survive(stores) -> None:
    """The second override amends the record the first one left, rather than
    replacing it — an audit trail is the point of keeping it."""
    client, results, evaluation_id = stores
    _check_one_label(client)
    _check_one_label(client, "another.png")

    for disposition in ("fail", "needs_review"):
        response = client.post(
            f"/labels/{evaluation_id}/overrides",
            json={
                "field_name": None,
                "applied_disposition": disposition,
                "reason_code": _REASON_CODE,
                "justification_text": None,
            },
        )
        assert response.status_code == 200, response.text

    kept = results.get(evaluation_id)
    assert kept is not None
    assert [o.applied_disposition for o in kept.audit_trail.overrides] == ["fail", "needs_review"]


def test_an_unknown_evaluation_still_answers_not_found(stores) -> None:
    client, _results, _evaluation_id = stores
    response = client.post(
        "/labels/ev-000000000000/overrides",
        json={
            "field_name": None,
            "applied_disposition": "fail",
            "reason_code": _REASON_CODE,
            "justification_text": None,
        },
    )
    assert response.status_code == 404
    assert "no result to override" in response.json()["detail"]
