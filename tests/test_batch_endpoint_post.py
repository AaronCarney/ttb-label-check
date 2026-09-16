"""POST /batches and GET /batches/{batch_id} — basic shape, and what a batch
of bare references actually gets back."""
import json

import httpx
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


@pytest.mark.asyncio
async def test_post_batches_refuses_every_item_by_name_when_no_image_was_supplied():
    """A batch of bare references is answered, item by item, with a refusal.

    `POST /batches` takes references to labels the caller says the server
    already has, and the app has no store to resolve a reference to an image.
    Before `docs/decisions.md#0020` the worker made up eight bytes of PNG header
    for each one and ran the reader, the rules and the disposition over them, so
    the caller got a verdict about a label nobody had ever seen. Now each item
    comes back `needs_review` naming `ENGINE.INPUT.LABEL_IMAGE_MISSING`, the
    whole batch is still walked, and the snapshot carries a sentence per item
    saying what to do instead (`docs/PRD.md` FR-13).

    The batch path that does carry images is `POST /batches/upload`; see
    `tests/test_batch_integration_smoke.py`.
    """
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = _stub_envelope(n_items=3)
        post_resp = await client.post("/batches", json=payload)
        assert post_resp.status_code == 202, post_resp.text
        batch_id = post_resp.json()["batch_id"]

        # SSE puts the name and the payload on separate lines, so carry the
        # name forward to the `data:` that belongs to it.
        events: list[tuple[str, dict]] = []
        name = ""
        async with client.stream("GET", f"/batches/{batch_id}/stream") as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    events.append((name, json.loads(line.split(":", 1)[1].strip())))
                    if name == "stream-end":
                        break

        snapshot = (await client.get(f"/batches/{batch_id}")).json()

    # Every item produced a result event, and the batch ended once.
    assert [name for name, _ in events] == [
        "label-result", "label-result", "label-result", "stream-end",
    ], events
    label_events = [data for _, data in events[:3]]
    end_event = events[3][1]
    assert [e["queue_position"] for e in label_events] == [0, 1, 2]
    assert end_event["total_count"] == 3
    assert end_event["failed_count"] == 3

    # Each envelope refuses by name rather than reporting a verdict.
    for event in label_events:
        envelope = event["envelope"]
        assert envelope["disposition"] == "needs_review", envelope
        assert envelope["fields"] == []
        trace = envelope["audit_trail"]["per_rule_trace"]
        assert [t["rule_id"] for t in trace] == ["ENGINE.INPUT.LABEL_IMAGE_MISSING"]

    # The snapshot shows each item failed, with a sentence naming that item.
    assert [item["state"] for item in snapshot["items"]] == ["failed"] * 3
    for i, item in enumerate(snapshot["items"]):
        reason = item["failed_reason"]
        assert reason, item
        assert f"lbl-{i}" in reason, reason
        assert "upload" in reason.lower(), reason
