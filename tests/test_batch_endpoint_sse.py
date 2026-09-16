"""GET /batches/{batch_id}/stream — SSE per-label events + stream-end."""
import asyncio

import httpx
import pytest

from app.main import create_app


@pytest.mark.asyncio
async def test_sse_stream_emits_per_label_events_then_stream_end_for_3_item_batch(monkeypatch):
    """3-item batch with fast fake evaluator → 3 label-result + 1 stream-end events."""
    from tests.conftest import _fake_evaluator

    # Override the evaluator factory before app boot so the worker uses the fake.
    monkeypatch.setattr(
        "app.deps.build_evaluator",
        lambda settings: _fake_evaluator(n_items=3, latency_s=0.05),
    )
    app = create_app()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        from datetime import datetime, timezone
        from app.schemas.wire.batch import BatchEnvelope, BatchItemRef
        payload = BatchEnvelope(
            batch_id="B-sse-001",
            agent_id="a",
            submitted_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc),
            items=tuple(
                BatchItemRef(label_ref=f"lbl-{i}", application_ref=f"app-{i:04d}")
                for i in range(3)
            ),
        ).model_dump(mode="json")
        post_resp = await client.post("/batches", json=payload)
        assert post_resp.status_code == 202

        # Open SSE stream
        events = []
        async with client.stream("GET", "/batches/B-sse-001/stream") as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    events.append(line.split(":", 1)[1].strip())
                if "stream-end" in line:
                    break

        assert events.count("label-result") == 3
        assert events.count("stream-end") == 1
        # Order
        assert events[-1] == "stream-end"


@pytest.mark.asyncio
async def test_sse_subscriber_pruned_within_1s_on_client_disconnect(monkeypatch):
    """On client disconnect the subscriber is removed within a second, and the
    worker carries on with the rest of the batch."""
    from tests.conftest import _fake_evaluator

    monkeypatch.setattr(
        "app.deps.build_evaluator",
        lambda settings: _fake_evaluator(n_items=10, latency_s=0.1),
    )
    app = create_app()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        from datetime import datetime, timezone
        from app.schemas.wire.batch import BatchEnvelope, BatchItemRef
        payload = BatchEnvelope(
            batch_id="B-sse-002",
            agent_id="a",
            submitted_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc),
            items=tuple(
                BatchItemRef(label_ref=f"lbl-{i}", application_ref=f"app-{i:04d}")
                for i in range(10)
            ),
        ).model_dump(mode="json")
        await client.post("/batches", json=payload)

        # Open and close fast
        async with client.stream("GET", "/batches/B-sse-002/stream") as resp:
            await resp.aiter_lines().__anext__()  # read 1 line
            # context-manager exit closes connection

        # Verify subscriber pruned within 1s. SSE subscribers live on the
        # per-batch SSEBus stored in `app.state.buses[batch_id]`, not on
        # InFlightBatch.
        bus = app.state.buses["B-sse-002"]
        for _ in range(20):  # poll up to 1 s @ 50ms
            await asyncio.sleep(0.05)
            if len(bus.subscribers) == 0:
                break
        assert len(bus.subscribers) == 0


@pytest.mark.asyncio
async def test_post_batches_rejects_duplicate_batch_id_with_409(monkeypatch):
    """409 collision: re-POST of an in-flight `batch_id` is rejected."""
    from datetime import datetime, timezone

    from app.schemas.wire.batch import BatchEnvelope, BatchItemRef
    from tests.conftest import _fake_evaluator

    monkeypatch.setattr(
        "app.deps.build_evaluator",
        lambda settings: _fake_evaluator(n_items=2, latency_s=0.5),
    )
    app = create_app()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            payload = BatchEnvelope(
                batch_id="B-dup",
                agent_id="a",
                submitted_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc),
                items=tuple(
                    BatchItemRef(label_ref=f"lbl-{i}", application_ref=f"app-{i:04d}")
                    for i in range(2)
                ),
            ).model_dump(mode="json")
            r1 = await client.post("/batches", json=payload)
            assert r1.status_code == 202
            r2 = await client.post("/batches", json=payload)
            assert r2.status_code == 409
            assert "B-dup" in r2.json()["detail"]
