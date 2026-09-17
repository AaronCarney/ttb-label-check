"""A batch worker must be held onto while it runs.

`asyncio.create_task` hands back the only strong reference to a task; the
event loop keeps a weak one. A caller that drops it lets the garbage collector
take a task mid-execution, and asyncio's own documentation says to save the
result for exactly that reason. Both places that start a `BatchWorker` dropped
it, so a submitted batch could stop being worked with nothing logged and
nothing raised — the batch would simply sit at the state it had reached.

The collection itself is not something a test can force, so what is asserted
is the reference: while a worker is running, the application holds it.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import _background
from app.batch.worker import BatchWorker
from app.main import create_app
from app.schemas.wire.batch import BatchEnvelope, BatchItemRef


def _envelope(batch_id: str = "B-task-ref-001") -> dict:
    return BatchEnvelope(
        batch_id=batch_id,
        agent_id="agent-mvp",
        submitted_at=datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC),
        items=(BatchItemRef(label_ref="lbl-0", application_ref="app-0000"),),
    ).model_dump(mode="json")


def test_app_state_starts_with_an_empty_task_set() -> None:
    app = create_app()
    assert app.state.batch_tasks == set()


@pytest.mark.asyncio
async def test_spawn_holds_a_running_task_and_releases_a_finished_one() -> None:
    app = create_app()
    release = asyncio.Event()

    async def _work() -> None:
        await release.wait()

    task = _background.spawn(app, _work(), name="unit")
    assert task in app.state.batch_tasks, "a running task must be referenced"

    release.set()
    await task
    await asyncio.sleep(0)  # let the done callback run
    assert task not in app.state.batch_tasks, "a finished task must be released"


@pytest.mark.asyncio
async def test_posting_a_batch_leaves_the_worker_task_referenced(monkeypatch) -> None:
    """The route holds the worker for as long as the worker runs."""
    app = create_app()
    release = asyncio.Event()

    async def _blocking_run(self) -> None:
        await release.wait()

    monkeypatch.setattr(BatchWorker, "run", _blocking_run)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/batches", json=_envelope())
        assert resp.status_code == 202, resp.text
        assert app.state.batch_tasks, (
            "the worker task was started and its only strong reference dropped; "
            "the garbage collector may take it mid-run"
        )
    release.set()
    await asyncio.gather(*list(app.state.batch_tasks), return_exceptions=True)


@pytest.mark.asyncio
async def test_drain_cancels_a_worker_that_is_still_running() -> None:
    """Shutdown says it evicts every in-flight batch. A worker still running
    against the state being cleared would make that claim false."""
    app = create_app()
    never = asyncio.Event()

    async def _work() -> None:
        await never.wait()

    task = _background.spawn(app, _work(), name="unit")
    cancelled = await _background.drain(app)

    assert cancelled == 1
    assert task.cancelled()
    assert app.state.batch_tasks == set()


def test_shutdown_leaves_no_worker_task_behind() -> None:
    app = create_app()
    with TestClient(app) as client:
        client.post("/batches", json=_envelope("B-task-ref-002"))
    assert app.state.batch_tasks == set()
