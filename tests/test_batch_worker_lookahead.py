"""BatchWorker lookahead and pull-based demand.

Two different windows share the name `lookahead_k`, and the difference is the
point of `docs/decisions.md#0021`. The queue's window bounds how many items are
*fetched* ahead, which costs nothing because the producer reads a tuple already
in memory. The demand gate bounds how many are *evaluated* ahead of the
reviewer who is reading the results, which is where the work actually is.
"""

import asyncio
import contextlib
from datetime import UTC, datetime

import pytest

from app.api._sse_bus import SSEBus
from app.batch.anomaly import AnomalyDetector
from app.batch.state import InFlightBatch
from app.batch.worker import BatchWorker
from app.schemas.batch import BatchItem, ItemState
from app.schemas.label import Face, Label
from tests.conftest import _fake_evaluator

# A tiny valid PNG. The fake evaluators here never read the bytes, but the
# worker refuses any item it has no image for (`docs/decisions.md#0020`), and a
# refused item never reaches the evaluator — which would make every timing
# assertion in this file vacuous.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "89000000017352474200aece1ce90000000d4944415478da636060606000000005"
    "0001a5f645400000000049454e44ae426082"
)


def _stub_item(idx: int) -> BatchItem:
    return BatchItem(
        label_id=f"lbl-{idx}",
        application_ref=f"app-{idx:04d}",
        state=ItemState.QUEUED,
        result=None,
        enqueued_at=datetime(2026, 5, 4, 12, 0, idx, tzinfo=UTC),
    )


def _label_lookup_for(items, batch_id: str) -> dict[str, Label]:
    """An image for every queued item, as the bulk-upload route supplies."""
    return {
        item.label_id: Label(
            label_id=item.label_id,
            batch_id=batch_id,
            faces=(
                Face(
                    image_bytes=_PNG_1x1,
                    content_type="image/png",
                    face_tag="front",
                ),
            ),
        )
        for item in items
    }


@pytest.mark.asyncio
async def test_worker_queue_saturates_at_lookahead_plus_one_when_consumer_holds():
    """When the consumer doesn't drain, the producer's queue saturates
    at maxsize=k+1=4 (lookahead_k=3)."""
    items = tuple(_stub_item(i) for i in range(10))
    in_flight = InFlightBatch(
        batch_id="B-LA1",
        agent_id="a",
        items=items,
        lookahead_k=3,
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
        label_lookup=_label_lookup_for(items, "B-LA1"),
    )

    run_task = asyncio.create_task(worker.run())
    # Give the producer time to fill the queue
    await asyncio.sleep(0.1)
    assert in_flight.queue.qsize() <= 4
    assert in_flight.queue.saturated is True
    run_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await run_task


@pytest.mark.asyncio
async def test_worker_lookahead_k_3_pre_fetches_next_two_items_while_one_processes():
    """When item N is being evaluated, items N+1 and N+2 are already in
    the queue (state ItemState.PROCESSING in spirit; verified here by checking
    `qsize` mid-evaluation)."""
    items = tuple(_stub_item(i) for i in range(5))
    in_flight = InFlightBatch(
        batch_id="B-LA2",
        agent_id="a",
        items=items,
        lookahead_k=3,
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
        label_lookup=_label_lookup_for(items, "B-LA2"),
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


@pytest.mark.asyncio
async def test_worker_holds_evaluations_while_the_reviewer_is_behind_and_resumes_on_drain():
    """A reviewer who stops reading stops the spending, and starts it again.

    This is the demand gate of `docs/decisions.md#0021`. A subscriber that is
    attached but not reading may fall at most `lookahead_k` results behind
    before the consumer holds, so a 300-label batch cannot run to the end — and
    bill a vision model 300 times — for someone still looking at label one.
    Once the reviewer reads, the rest of the batch runs.
    """
    k = 3
    items = tuple(_stub_item(i) for i in range(12))
    in_flight = InFlightBatch(
        batch_id="B-LA3",
        agent_id="a",
        items=items,
        lookahead_k=k,
    )

    from tests.conftest import _stub_disposition_envelope

    class _CountingEvaluator:
        def __init__(self) -> None:
            self.calls = 0

        async def evaluate(self, application, label):
            self.calls += 1
            return _stub_disposition_envelope(self.calls - 1)

    evaluator = _CountingEvaluator()
    bus = SSEBus()
    sub = bus.subscribe()  # attached, and deliberately not read from yet
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=evaluator,
        anomaly=AnomalyDetector(),
        bus=bus,
        label_lookup=_label_lookup_for(items, "B-LA3"),
    )

    run_task = asyncio.create_task(worker.run())

    # Long enough that an ungated worker — the evaluator returns instantly —
    # would have finished all twelve many times over.
    await asyncio.sleep(0.2)

    assert not run_task.done(), "the worker ran to completion with nobody reading"
    assert evaluator.calls == k + 1, (
        f"expected the gate to hold after {k + 1} evaluations, got {evaluator.calls}"
    )

    # The reviewer starts reading. The batch finishes.
    events: list[dict] = []
    while True:
        evt = await asyncio.wait_for(sub.get(), timeout=5.0)
        events.append(evt)
        if evt["event"] == "stream-end":
            break
    await asyncio.wait_for(run_task, timeout=1.0)

    assert evaluator.calls == 12
    assert [e["event"] for e in events].count("label-result") == 12
    assert events[-1]["data"]["failed_count"] == 0


@pytest.mark.asyncio
async def test_worker_is_not_paced_when_no_reviewer_is_attached():
    """With nobody reading, nothing is held back.

    The JSON API caller who polls `GET /batches/{batch_id}` never opens the
    stream, so the gate must be inert for them rather than stalling the batch
    forever (`docs/decisions.md#0021`).
    """
    items = tuple(_stub_item(i) for i in range(12))
    in_flight = InFlightBatch(
        batch_id="B-LA4",
        agent_id="a",
        items=items,
        lookahead_k=3,
    )
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=_fake_evaluator(n_items=12, latency_s=0.0),
        anomaly=AnomalyDetector(),
        bus=SSEBus(),  # no subscriber
        label_lookup=_label_lookup_for(items, "B-LA4"),
    )

    await asyncio.wait_for(worker.run(), timeout=2.0)

    assert len(in_flight.results) == 12
    assert in_flight.current_index == 12
