"""POST /batches and GET /batches/{batch_id} — basic shape."""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.wire.batch import BatchEnvelope, BatchItemRef


def _stub_envelope(n_items: int = 3) -> dict:
    return BatchEnvelope(
        batch_id="B-test-001",
        agent_id="agent-mvp",
        submitted_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc),
        items=tuple(
            BatchItemRef(label_ref=f"lbl-{i}", application_ref=f"app-{i:04d}")
            for i in range(n_items)
        ),
    ).model_dump(mode="json")


def test_post_batches_returns_202_and_batch_id():
    app = create_app()
    with TestClient(app) as client:
        payload = _stub_envelope(n_items=3)
        resp = client.post("/batches", json=payload)
        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert "batch_id" in body
        assert body["batch_id"] == payload["batch_id"]


def test_post_batches_rejects_malformed_envelope_with_400():
    app = create_app()
    with TestClient(app) as client:
        resp = client.post("/batches", json={"foo": "bar"})
        assert resp.status_code in (400, 422), resp.text  # Pydantic validation


def test_get_batches_returns_snapshot():
    app = create_app()
    with TestClient(app) as client:
        payload = _stub_envelope(n_items=2)
        post_resp = client.post("/batches", json=payload)
        assert post_resp.status_code == 202
        batch_id = post_resp.json()["batch_id"]

        get_resp = client.get(f"/batches/{batch_id}")
        assert get_resp.status_code == 200
        snap = get_resp.json()
        assert snap["batch_id"] == batch_id
        assert snap["agent_id"] == "agent-mvp"
        assert len(snap["items"]) == 2


def test_get_batches_unknown_batch_id_returns_404():
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/batches/B-does-not-exist")
        assert resp.status_code == 404
