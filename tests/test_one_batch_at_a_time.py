"""The service checks one batch at a time, and keeps no batch it is finished with.

A batch is a demonstration: the reviewer uploads a set, is taken straight to its
results, and watches them arrive. A second batch started while the first is
still being checked would compete with it for the one reader, and a finished
batch kept after the next one starts is memory nobody will ask for again
(`docs/decisions.md#0041`).

There is no login, so "one at a time" is one per running service, not one per
person: while a batch runs, anyone else who uploads is told to wait.

Every check is a batch now, including a batch of one (`docs/decisions.md#0045`),
so the wait reaches a reviewer checking a single label while someone else's
three hundred are running. That is a real cost of the merge and it is asserted
here rather than left to be discovered.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.api.ui import _get_upload_evaluator
from app.main import create_app
from tests.conftest import _stub_disposition_envelope
from tests.test_batch_worker_skeleton import _label_lookup_for, _PNG_1x1, _stub_item


class _GatedEvaluator:
    """Holds every evaluation until the test opens the gate."""

    def __init__(self) -> None:
        self.gate = asyncio.Event()
        self.calls = 0

    async def evaluate(self, application, label):
        self.calls += 1
        await self.gate.wait()
        return _stub_disposition_envelope(self.calls)


def _files(n: int) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("labels", (f"label-{i}.png", _PNG_1x1, "image/png")) for i in range(n)]


async def _upload(client: httpx.AsyncClient, n: int = 2) -> httpx.Response:
    return await client.post("/", files=_files(n), data={"beverage_type": "wine"})


async def _finish(app) -> None:
    await asyncio.gather(*list(app.state.batch_tasks))


@pytest.fixture
def gated():
    app = create_app()
    evaluator = _GatedEvaluator()
    app.dependency_overrides[_get_upload_evaluator] = lambda: evaluator
    return app, evaluator


async def test_a_second_upload_is_refused_while_the_first_is_being_checked(gated) -> None:
    app, evaluator = gated
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await _upload(client)
        assert first.status_code == 303, first.text
        first_id = first.headers["location"].removeprefix("/batch/")

        second = await _upload(client)
        assert second.status_code == 409, second.text
        assert "one batch at a time" in second.text
        assert "0 of 2" in second.text
        assert list(app.state.batches) == [first_id]

        evaluator.gate.set()
        await _finish(app)


async def test_the_api_route_is_refused_while_an_upload_is_being_checked(gated) -> None:
    app, evaluator = gated
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await _upload(client)).status_code == 303
        refs = {
            "batch_id": "B-api",
            "agent_id": "agent",
            "submitted_at": "2026-01-01T00:00:00Z",
            "items": [{"label_ref": "lbl-0", "application_ref": "app-0000"}],
        }
        response = await client.post("/batches", json=refs)
        assert response.status_code == 409, response.text
        assert "one batch at a time" in response.json()["detail"]

        evaluator.gate.set()
        await _finish(app)


async def test_one_label_waits_for_a_running_batch_too(gated) -> None:
    """The cost of one system. A reviewer with a single label used to have a
    path of its own that was never refused; now it is a batch of one and it
    queues behind whatever is running, like everything else."""
    app, evaluator = gated
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await _upload(client, 2)).status_code == 303

        one_label = await _upload(client, 1)
        assert one_label.status_code == 409, one_label.text
        assert "one batch at a time" in one_label.text

        evaluator.gate.set()
        await _finish(app)


async def test_a_new_batch_drops_the_finished_one(gated) -> None:
    app, evaluator = gated
    evaluator.gate.set()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await _upload(client)
        first_id = first.headers["location"].removeprefix("/batch/")
        await _finish(app)
        assert (await client.get(f"/batches/{first_id}")).status_code == 200

        second = await _upload(client)
        assert second.status_code == 303, second.text
        second_id = second.headers["location"].removeprefix("/batch/")
        await _finish(app)

        assert (await client.get(f"/batches/{first_id}")).status_code == 404
        assert list(app.state.batches) == [second_id]
        assert list(app.state.buses) == [second_id]


async def test_each_image_is_let_go_once_its_label_is_checked() -> None:
    """The worker holds a label's image only until that label is checked.

    The bytes go as soon as the result is recorded — and, where the submission
    came from the form, written to the store the results page fetches them
    from. Holding them in the worker instead would mean a batch carrying every
    upload until its last label is done. Measured at each evaluation: the
    labels still held are the one being checked and the ones after it.
    """
    from app.api._sse_bus import SSEBus
    from app.batch.anomaly import AnomalyDetector
    from app.batch.state import InFlightBatch
    from app.batch.worker import BatchWorker

    items = tuple(_stub_item(i) for i in range(3))
    lookup = _label_lookup_for(items, "B-drop")
    held: list[int] = []

    class _Counting:
        async def evaluate(self, application, label):
            held.append(len(lookup))
            return _stub_disposition_envelope(len(held))

    worker = BatchWorker(
        in_flight=InFlightBatch(batch_id="B-drop", agent_id="a", items=items),
        evaluator=_Counting(),
        anomaly=AnomalyDetector(),
        bus=SSEBus(),
        label_lookup=lookup,
    )
    await worker.run()

    assert held == [3, 2, 1]
    assert lookup == {}
