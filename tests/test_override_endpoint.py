"""POST /labels/{evaluation_id}/overrides — happy path + validation."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def _seed_a_batch_with_one_completed_item(app):
    """Helper: drive a 1-item batch through and wait for completion so the
    override endpoint has a valid evaluation_id to target."""
    from app.batch.anomaly import AnomalyDetector
    from app.batch.state import InFlightBatch
    from app.batch.worker import BatchWorker
    from app.api._sse_bus import SSEBus
    from app.schemas.batch import BatchItem, ItemState
    from tests.conftest import _fake_evaluator, _stub_disposition_envelope

    item = BatchItem(
        label_id="lbl-0",
        application_ref="app-0000",
        state=ItemState.QUEUED,
        result=None,
        enqueued_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc),
    )
    env = _stub_disposition_envelope(0, disposition="needs_review")
    in_flight = InFlightBatch(batch_id="B-OV", agent_id="a", items=(item,), lookahead_k=3)
    in_flight.results["lbl-0"] = env
    app.state.batches["B-OV"] = in_flight
    if not hasattr(app.state, "buses"):
        app.state.buses = {}
    app.state.buses["B-OV"] = SSEBus()
    return env


def test_post_override_records_entry_and_returns_200():
    app = create_app()
    app.state.batches = {}  # ensure fresh
    env = _seed_a_batch_with_one_completed_item(app)
    client = TestClient(app)

    payload = {
        "reason_code": "BRAND.NAME.NEEDS_REVIEW",
        "applied_disposition": "pass",
        "justification_text": "Looks correct on review.",
    }
    resp = client.post(f"/labels/{env.evaluation_id}/overrides", json=payload)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["original_disposition"] == "needs_review"
    assert body["applied_disposition"] == "pass"
    assert body["reason_code"] == "BRAND.NAME.NEEDS_REVIEW"
    assert body["justification_text"] == "Looks correct on review."
    assert body["reviewer_id"].startswith("session-")
    assert "timestamp" in body


def test_post_override_rejects_unknown_reason_code():
    app = create_app()
    app.state.batches = {}
    env = _seed_a_batch_with_one_completed_item(app)
    client = TestClient(app)

    payload = {
        "reason_code": "BRAND.NAME.NOT.IN.REGISTRY",  # bogus
        "applied_disposition": "pass",
    }
    resp = client.post(f"/labels/{env.evaluation_id}/overrides", json=payload)
    assert resp.status_code == 400
    assert "reason_code" in resp.json()["detail"].lower()


def test_post_override_rejects_unknown_evaluation_id():
    app = create_app()
    app.state.batches = {}
    client = TestClient(app)
    payload = {"reason_code": "BRAND.NAME.NEEDS_REVIEW", "applied_disposition": "pass"}
    resp = client.post("/labels/EV-DOES-NOT-EXIST/overrides", json=payload)
    assert resp.status_code == 404


def test_post_override_with_field_name_records_field_specific_entry():
    app = create_app()
    app.state.batches = {}
    env = _seed_a_batch_with_one_completed_item(app)
    client = TestClient(app)

    payload = {
        "field_name": "brand_name",
        "reason_code": "BRAND.NAME.NEEDS_REVIEW",
        "applied_disposition": "pass",
    }
    resp = client.post(f"/labels/{env.evaluation_id}/overrides", json=payload)
    assert resp.status_code == 200
    assert resp.json()["field_name"] == "brand_name"
