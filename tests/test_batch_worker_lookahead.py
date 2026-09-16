"""BatchWorker lookahead and pull-based demand."""
import asyncio
from datetime import datetime, timezone

import pytest

from app.api._sse_bus import SSEBus
from app.batch.anomaly import AnomalyDetector
from app.batch.state import InFlightBatch
from app.batch.worker import BatchWorker
from app.schemas.batch import BatchItem, ItemState
from tests.conftest import _fake_evaluator


def _stub_item(idx: int) -> BatchItem:
    return BatchItem(
        label_id=f"lbl-{idx}",
        application_ref=f"app-{idx:04d}",
        state=ItemState.QUEUED,
        result=None,
        enqueued_at=datetime(2026, 5, 4, 12, 0, idx, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_worker_queue_saturates_at_lookahead_plus_one_when_consumer_holds():
    """When the consumer doesn't drain, the producer's queue saturates
    at maxsize=k+1=4 (lookahead_k=3)."""
    items = tuple(_stub_item(i) for i in range(10))
    in_flight = InFlightBatch(
        batch_id="B-LA1", agent_id="a", items=items, lookahead_k=3,
    )

    # FakeEvaluator that NEVER returns — we drive saturation by holding the
    # consumer indefinitely.
    class _BlockingEvaluator:
        async def evaluate(self, app, label):
            await asyncio.Event().wait()  # never resolves

    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=_BlockingEvaluator(),
        anomaly=AnomalyDetector(),
        bus=SSEBus(),
    )

    run_task = asyncio.create_task(worker.run())
    # Give the producer time to fill the queue
    await asyncio.sleep(0.1)
    assert in_flight.queue.qsize() <= 4
    assert in_flight.queue.saturated is True
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_worker_lookahead_k_3_pre_fetches_next_two_items_while_one_processes():
    """When item N is being evaluated, items N+1 and N+2 are already in
    the queue (state ItemState.PROCESSING in spirit; verified here by checking
    `qsize` mid-evaluation)."""
    items = tuple(_stub_item(i) for i in range(5))
    in_flight = InFlightBatch(
        batch_id="B-LA2", agent_id="a", items=items, lookahead_k=3,
    )

    # Slow evaluator — 0.3s per call. After item 0 finishes, items 1, 2, 3
    # should be queued (k+1 = 4 capacity, but we only have 5 total items).
    fake_eval = _fake_evaluator(n_items=5, latency_s=0.3)
    bus = SSEBus()
    sub = bus.subscribe()
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=fake_eval,
        anomaly=AnomalyDetector(),
        bus=bus,
    )

    run_task = asyncio.create_task(worker.run())
    # Wait for item 0's event
    e0 = await asyncio.wait_for(sub.get(), timeout=1.0)
    assert e0["data"]["queue_position"] == 0

    # At this point item 1 is being evaluated; items 2, 3, 4 should be in
    # the queue (the producer fills eagerly until saturation or end).
    # We have 4 remaining items and maxsize=4 → all 4 in the queue.
    # But item 1 was just popped → 3 in the queue, 1 in flight.
    await asyncio.sleep(0.05)  # let producer top up
    assert in_flight.queue.qsize() >= 2, (
        f"expected at least 2 items pre-fetched, got qsize={in_flight.queue.qsize()}"
    )

    # Drain remaining
    for _ in range(4):
        await asyncio.wait_for(sub.get(), timeout=2.0)
    end_evt = await asyncio.wait_for(sub.get(), timeout=2.0)
    assert end_evt["event"] == "stream-end"
    await run_task
