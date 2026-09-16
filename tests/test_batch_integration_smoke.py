"""End-to-end canary: a 5-item batch with a fake evaluator over a real SSE
response. Drains the events and asserts five per-label events, a stream-end,
no advisories, and that the connection closes."""
import asyncio
from datetime import datetime, timezone

import httpx
import pytest


@pytest.mark.asyncio
async def test_5_item_batch_end_to_end_via_real_sse_response(monkeypatch):
    from app.main import create_app
    from app.schemas.wire.batch import BatchEnvelope, BatchItemRef
    from tests.conftest import _fake_evaluator

    monkeypatch.setattr(
        "app.deps.build_evaluator",
        lambda settings: _fake_evaluator(n_items=5, latency_s=0.3),
    )
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        envelope = BatchEnvelope(
            batch_id="B-canary-001",
            agent_id="a",
            submitted_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc),
            items=tuple(
                BatchItemRef(label_ref=f"lbl-{i}", application_ref=f"app-{i:04d}")
                for i in range(5)
            ),
        ).model_dump(mode="json")
        post_resp = await client.post("/batches", json=envelope)
        assert post_resp.status_code == 202

        events: list[str] = []
        async with client.stream("GET", "/batches/B-canary-001/stream") as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    events.append(line.split(":", 1)[1].strip())
                if "stream-end" in line:
                    break

        assert events.count("label-result") == 5
        assert events.count("anomaly-advisory") == 0  # no anomaly with 5 distinct
        assert events.count("stream-end") == 1
        assert events[-1] == "stream-end"


@pytest.mark.asyncio
async def test_5_item_batch_with_mid_batch_override_continues_to_completion(monkeypatch):
    """An override applied mid-batch does not stop the worker."""
    from app.main import create_app
    from app.schemas.wire.batch import BatchEnvelope, BatchItemRef
    from tests.conftest import _fake_evaluator, _stub_disposition_envelope

    plan = [(0.1, _stub_disposition_envelope(i, disposition="needs_review")) for i in range(5)]
    monkeypatch.setattr(
        "app.deps.build_evaluator",
        lambda settings: _fake_evaluator(plan=plan),
    )
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        envelope = BatchEnvelope(
            batch_id="B-canary-002",
            agent_id="a",
            submitted_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc),
            items=tuple(
                BatchItemRef(label_ref=f"lbl-{i}", application_ref=f"app-{i:04d}")
                for i in range(5)
            ),
        ).model_dump(mode="json")
        await client.post("/batches", json=envelope)

        events: list[dict] = []

        async def _drain():
            async with client.stream("GET", "/batches/B-canary-002/stream") as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("event:"):
                        events.append({"event": line.split(":", 1)[1].strip()})
                    if "stream-end" in line:
                        break

        # Run draining + override concurrently
        drain_task = asyncio.create_task(_drain())
        await asyncio.sleep(0.15)  # let item 0 land

        override_resp = await client.post(
            "/labels/EV-0000/overrides",
            json={
                "reason_code": "BRAND.NAME.NEEDS_REVIEW",
                "applied_disposition": "pass",
                "justification_text": "Mid-batch override",
            },
        )
        assert override_resp.status_code == 200

        await asyncio.wait_for(drain_task, timeout=5.0)

    label_count = sum(1 for e in events if e["event"] == "label-result")
    end_count = sum(1 for e in events if e["event"] == "stream-end")
    override_count = sum(1 for e in events if e["event"] == "override-applied")
    assert label_count == 5  # all items processed despite mid-batch override
    assert end_count == 1
    assert override_count == 1
