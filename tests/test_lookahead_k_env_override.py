"""AC #10: LOOKAHEAD_K=2 reduces lookahead to 2; LOOKAHEAD_K=4 increases to 4."""
import asyncio
from datetime import datetime, timezone

import httpx
import pytest


@pytest.mark.parametrize("k_value", [2, 4])
@pytest.mark.asyncio
async def test_lookahead_k_env_var_overrides_default_3(k_value, monkeypatch):
    from app.main import create_app
    from app.schemas.wire.batch import BatchEnvelope, BatchItemRef
    from tests.conftest import _fake_evaluator

    monkeypatch.setenv("LOOKAHEAD_K", str(k_value))
    monkeypatch.setattr(
        "app.deps.build_evaluator",
        lambda settings: _fake_evaluator(n_items=10, latency_s=0.5),
    )

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        envelope = BatchEnvelope(
            batch_id=f"B-LA-{k_value}",
            agent_id="a",
            submitted_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc),
            items=tuple(
                BatchItemRef(label_ref=f"lbl-{i}", application_ref=f"app-{i:04d}")
                for i in range(10)
            ),
        ).model_dump(mode="json")
        await client.post("/batches", json=envelope)
        # Inspect the in-flight batch directly
        in_flight = app.state.batches[f"B-LA-{k_value}"]
        assert in_flight.lookahead_k == k_value
        assert in_flight.queue.maxsize == k_value + 1


@pytest.mark.asyncio
async def test_lookahead_k_default_is_3_when_env_absent(monkeypatch):
    from app.main import create_app
    from app.schemas.wire.batch import BatchEnvelope, BatchItemRef
    from tests.conftest import _fake_evaluator

    monkeypatch.delenv("LOOKAHEAD_K", raising=False)
    monkeypatch.setattr(
        "app.deps.build_evaluator",
        lambda settings: _fake_evaluator(n_items=3, latency_s=0.1),
    )
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        envelope = BatchEnvelope(
            batch_id="B-LA-default",
            agent_id="a",
            submitted_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=timezone.utc),
            items=tuple(
                BatchItemRef(label_ref=f"lbl-{i}", application_ref=f"app-{i:04d}")
                for i in range(3)
            ),
        ).model_dump(mode="json")
        await client.post("/batches", json=envelope)
        in_flight = app.state.batches["B-LA-default"]
        assert in_flight.lookahead_k == 3
        assert in_flight.queue.maxsize == 4
