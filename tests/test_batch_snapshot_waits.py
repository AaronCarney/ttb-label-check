"""GET /batches/{batch_id} holds the request open until the batch is checked.

Cloud Run allocates CPU to the service only while a request is open, and a
batch is worked after the request that started it has returned. A client that
asked for the snapshot and hung up at once left the worker with no CPU between
its requests, and every label ran into the evaluation guard. Holding the
snapshot request until the batch is done keeps CPU allocated for exactly as
long as someone is waiting on it (`docs/decisions.md#0049`).
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import httpx
import pytest

from app.api import _background
from app.api.batches import _get_settings
from app.batch.state import InFlightBatch
from app.config import Settings
from app.main import create_app
from app.schemas.batch import BatchItem, ItemState

WORK_SECONDS = 0.5


def _register(app, batch_id: str) -> None:
    """A two-item batch whose worker runs for WORK_SECONDS and records nothing."""
    items = tuple(
        BatchItem(
            label_id=f"{batch_id}-{i:03d}",
            application_ref=f"{batch_id}-app-{i:03d}",
            state=ItemState.QUEUED,
            result=None,
            enqueued_at=datetime.now(UTC),
        )
        for i in range(2)
    )
    app.state.batches[batch_id] = InFlightBatch(batch_id=batch_id, agent_id="t", items=items)
    _background.spawn(app, asyncio.sleep(WORK_SECONDS), name=f"batch-worker:{batch_id}")


async def _timed_get(app, url: str) -> tuple[httpx.Response, float]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        started = time.monotonic()
        response = await client.get(url)
        return response, time.monotonic() - started


def _app(wait_cap: float = 600.0):
    app = create_app()
    app.state.batches = {}
    app.state.buses = {}
    app.state.batch_tasks = set()
    settings = Settings(SNAPSHOT_WAIT_SECONDS=wait_cap)
    app.dependency_overrides[_get_settings] = lambda: settings
    return app


@pytest.mark.asyncio
async def test_the_snapshot_answers_once_the_batch_is_checked():
    app = _app()
    _register(app, "B-wait")
    response, elapsed = await _timed_get(app, "/batches/B-wait")
    assert response.status_code == 200
    assert elapsed >= WORK_SECONDS * 0.9


@pytest.mark.asyncio
async def test_wait_zero_answers_at_once():
    app = _app()
    _register(app, "B-now")
    response, elapsed = await _timed_get(app, "/batches/B-now?wait=0")
    assert response.status_code == 200
    assert elapsed < WORK_SECONDS / 2
    assert [item["state"] for item in response.json()["items"]] == ["queued", "queued"]


@pytest.mark.asyncio
async def test_the_wait_is_bounded_by_the_service_cap():
    app = _app(wait_cap=0.1)
    _register(app, "B-cap")
    response, elapsed = await _timed_get(app, "/batches/B-cap")
    assert response.status_code == 200
    assert elapsed < WORK_SECONDS / 2


@pytest.mark.asyncio
async def test_a_finished_batch_answers_at_once():
    app = _app()
    _register(app, "B-done")
    await asyncio.sleep(WORK_SECONDS * 1.2)
    response, elapsed = await _timed_get(app, "/batches/B-done")
    assert response.status_code == 200
    assert elapsed < WORK_SECONDS / 2
