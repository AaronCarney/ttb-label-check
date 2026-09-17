"""A reviewer can overrule a single label, not only one inside a batch.

The override endpoint used to search in-flight batches and nothing else, and a
single-label check kept no result at all, so every override against one
answered 404. These drive the real routes end to end: upload, override, and
read the record back.
"""

from __future__ import annotations

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
def stores(tmp_path: Path) -> tuple[TestClient, SingleResultStore, str]:
    """The real app with both stores under the test's own directory."""
    envelope = _stub_disposition_envelope(7, disposition="pass")
    results = SingleResultStore(tmp_path / "results")
    app = create_app()
    app.dependency_overrides[_get_upload_evaluator] = lambda: FakeEvaluator([(0.0, envelope)])
    app.dependency_overrides[_get_image_store] = lambda: UploadImageStore(tmp_path / "images")
    app.dependency_overrides[_get_result_store] = lambda: results
    return TestClient(app), results, envelope.evaluation_id


def test_single_label_override_is_recorded(stores) -> None:
    client, results, evaluation_id = stores

    upload = client.post("/", files={"label": ("label.png", _png_1x1(), "image/png")})
    assert upload.status_code == 200

    # The check is not in any batch — this is the case that used to 404.
    assert client.app.state.batches == {}

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
    assert (
        client.post("/", files={"label": ("label.png", _png_1x1(), "image/png")}).status_code == 200
    )

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
