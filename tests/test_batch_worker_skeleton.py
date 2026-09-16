"""BatchWorker basics: a single-item batch consumed end to end, and the first
label of a long batch returned without waiting for the rest."""
import asyncio
import time
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
async def test_worker_processes_single_item_and_emits_label_result_then_stream_end():
    in_flight = InFlightBatch(
        batch_id="B-001",
        agent_id="a",
        items=(_stub_item(0),),
        lookahead_k=3,
    )
    bus = SSEBus()
    sub = bus.subscribe()
    fake_eval = _fake_evaluator(n_items=1, latency_s=0.0)
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=fake_eval,
        anomaly=AnomalyDetector(),
        bus=bus,
    )

    await worker.run()

    # Two events: label-result + stream-end
    e1 = await asyncio.wait_for(sub.get(), timeout=0.5)
    e2 = await asyncio.wait_for(sub.get(), timeout=0.5)
    assert e1["event"] == "label-result"
    assert e1["data"]["queue_position"] == 0
    assert e1["data"]["batch_id"] == "B-001"
    assert e2["event"] == "stream-end"
    assert e2["data"]["batch_id"] == "B-001"
    assert e2["data"]["total_count"] == 1


@pytest.mark.asyncio
async def test_worker_records_result_and_advances_current_index():
    in_flight = InFlightBatch(
        batch_id="B-002",
        agent_id="a",
        items=(_stub_item(0), _stub_item(1)),
        lookahead_k=3,
    )
    fake_eval = _fake_evaluator(n_items=2, latency_s=0.0)
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=fake_eval,
        anomaly=AnomalyDetector(),
        bus=SSEBus(),
    )

    await worker.run()

    assert set(in_flight.results.keys()) == {"lbl-0", "lbl-1"}
    assert in_flight.current_index == 2  # both items completed


@pytest.mark.asyncio
async def test_worker_first_label_individual_does_not_wait_for_lookahead_window():
    """The first label of a 50-item batch returns inside the latency budget even
    when subsequent items take a long time. The worker must NOT batch the
    first item with later items."""
    items = tuple(_stub_item(i) for i in range(50))
    in_flight = InFlightBatch(
        batch_id="B-003", agent_id="a", items=items, lookahead_k=3,
    )
    bus = SSEBus()
    sub = bus.subscribe()

    # Item 0 is fast; items 1+ are slow. If the worker waited for lookahead k=3
    # to fill before responding, we'd see a delay of at least 3 * 0.5 = 1.5s
    # before item 0's event. With first-label-individual, item 0 emits in <0.1s.
    from tests.conftest import _stub_disposition_envelope
    plan = [(0.0, _stub_disposition_envelope(0))] + [
        (0.5, _stub_disposition_envelope(i)) for i in range(1, 50)
    ]
    fake_eval = _fake_evaluator(plan=plan)
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=fake_eval,
        anomaly=AnomalyDetector(),
        bus=bus,
    )

    t0 = time.perf_counter()
    run_task = asyncio.create_task(worker.run())
    first_event = await asyncio.wait_for(sub.get(), timeout=2.0)
    elapsed = time.perf_counter() - t0
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass

    assert first_event["event"] == "label-result"
    assert first_event["data"]["queue_position"] == 0
    assert elapsed < 0.5, f"first-label took {elapsed:.3f}s — exceeds 0.5s budget"


@pytest.mark.asyncio
async def test_worker_run_does_not_deadlock_when_consumer_raises():
    """Regression guard for the producer/consumer cancel-in-finally pattern.

    If `_consume` raises while the producer is parked on a saturated
    `queue.put`, the `finally` MUST cancel the producer task before
    awaiting it — otherwise `await producer_task` deadlocks. We assert
    the run() coroutine completes (with the consumer's exception
    propagated) inside a tight asyncio.wait_for timeout."""

    class _RaisingEvaluator:
        async def evaluate(self, application, label):
            raise RuntimeError("evaluator boom")

    in_flight = InFlightBatch(
        batch_id="B-RAISE", agent_id="a",
        items=tuple(_stub_item(i) for i in range(5)),
        lookahead_k=3,
    )
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=_RaisingEvaluator(),
        anomaly=AnomalyDetector(),
        bus=SSEBus(),
    )

    with pytest.raises(RuntimeError, match="evaluator boom"):
        await asyncio.wait_for(worker.run(), timeout=1.0)
