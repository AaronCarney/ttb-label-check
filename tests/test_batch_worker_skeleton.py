"""BatchWorker basics: a single-item batch consumed end to end, the first label
of a long batch returned without waiting for the rest, and one failing label
leaving the rest of the batch checked."""
import asyncio
import time
from datetime import UTC, datetime

import pytest

from app.api._sse_bus import SSEBus
from app.batch.anomaly import AnomalyDetector
from app.batch.state import InFlightBatch
from app.batch.worker import BatchWorker
from app.schemas.batch import BatchItem, ItemState
from app.schemas.label import Label
from tests.conftest import _fake_evaluator

# A tiny valid PNG. The evaluator in these tests is a fake and never reads the
# bytes, but the worker refuses any item it has no image for, so every item
# under test needs one (`docs/decisions.md#0020`).
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
            image_bytes=_PNG_1x1,
            content_type="image/png",
            face_tag="front",
        )
        for item in items
    }


async def _drain_until_stream_end(sub: asyncio.Queue, *, timeout: float = 5.0) -> list[dict]:
    """Read events as they are broadcast, stopping at `stream-end`.

    Reading concurrently with the worker is not an optional convenience: the
    consumer paces itself against the slowest attached subscriber, so a test
    that subscribes and never reads holds the batch on purpose
    (`docs/decisions.md#0021`)."""
    events: list[dict] = []
    while True:
        evt = await asyncio.wait_for(sub.get(), timeout=timeout)
        events.append(evt)
        if evt["event"] == "stream-end":
            return events


@pytest.mark.asyncio
async def test_worker_processes_single_item_and_emits_label_result_then_stream_end():
    items = (_stub_item(0),)
    in_flight = InFlightBatch(
        batch_id="B-001",
        agent_id="a",
        items=items,
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
        label_lookup=_label_lookup_for(items, "B-001"),
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
    # Nothing was refused: the item had an image and the evaluator answered.
    assert e2["data"]["failed_count"] == 0
    assert in_flight.failures == {}


@pytest.mark.asyncio
async def test_worker_records_result_and_advances_current_index():
    items = (_stub_item(0), _stub_item(1))
    in_flight = InFlightBatch(
        batch_id="B-002",
        agent_id="a",
        items=items,
        lookahead_k=3,
    )
    fake_eval = _fake_evaluator(n_items=2, latency_s=0.0)
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=fake_eval,
        anomaly=AnomalyDetector(),
        bus=SSEBus(),
        label_lookup=_label_lookup_for(items, "B-002"),
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
        label_lookup=_label_lookup_for(items, "B-003"),
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
    `queue.put`, the `finally` MUST cancel the producer task before awaiting
    it — otherwise `await producer_task` deadlocks. We assert the run()
    coroutine completes (with the consumer's exception propagated) inside a
    tight asyncio.wait_for timeout.

    The failure is driven through the bus rather than through the evaluator: an
    evaluator that raises is now caught per label and no longer reaches
    `_consume`'s caller at all (`docs/decisions.md#0020`), so it can no longer
    kill the consumer. A broadcast that raises still can, and it puts the
    consumer down at exactly the moment this guard exists for — the producer
    parked on a full queue. `stream-end` is let through so the guard is not
    confused by a second failure inside the `finally`.
    """

    class _RaisingBus(SSEBus):
        def broadcast(self, event: dict) -> None:
            if event.get("event") == "label-result":
                raise RuntimeError("broadcast boom")
            super().broadcast(event)

    # More items than the queue holds (maxsize = k + 1 = 4), so the producer is
    # certainly parked on a `put` when the consumer dies.
    items = tuple(_stub_item(i) for i in range(20))
    in_flight = InFlightBatch(
        batch_id="B-RAISE", agent_id="a", items=items, lookahead_k=3,
    )
    bus = _RaisingBus()
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=_fake_evaluator(n_items=20, latency_s=0.0),
        anomaly=AnomalyDetector(),
        bus=bus,
        label_lookup=_label_lookup_for(items, "B-RAISE"),
    )

    with pytest.raises(RuntimeError, match="broadcast boom"):
        await asyncio.wait_for(worker.run(), timeout=1.0)

    # The SSE client is not left hanging: the `finally` still sent a terminator
    # carrying the error class.
    assert bus._event_log[-1]["event"] == "stream-end"
    assert bus._event_log[-1]["data"]["error_class"] == "RuntimeError"


@pytest.mark.asyncio
async def test_worker_carries_on_when_one_label_evaluation_raises():
    """One bad label is refused by name; the other four are still checked.

    `docs/PRD.md` FR-13 requires the product to name the item at fault and
    check the rest of the batch. Before `docs/decisions.md#0020` the worker
    re-raised, so a batch of 300 labels ended at whichever one first upset the
    reader and the other 299 were never looked at.
    """
    items = tuple(_stub_item(i) for i in range(5))
    in_flight = InFlightBatch(
        batch_id="B-CARRY", agent_id="a", items=items, lookahead_k=3,
    )

    from tests.conftest import _stub_disposition_envelope

    class _RaisesOnSecondItem:
        """Fails item 2 of 5 and answers normally for the rest."""

        def __init__(self) -> None:
            self.calls = 0

        async def evaluate(self, application, label):
            self.calls += 1
            if self.calls == 2:
                raise ValueError("reader fell over on this one")
            return _stub_disposition_envelope(self.calls - 1)

    evaluator = _RaisesOnSecondItem()
    bus = SSEBus()
    sub = bus.subscribe()
    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=evaluator,
        anomaly=AnomalyDetector(),
        bus=bus,
        label_lookup=_label_lookup_for(items, "B-CARRY"),
    )

    run_task = asyncio.create_task(worker.run())
    events = await _drain_until_stream_end(sub)
    # run() returns normally — a failing label is not a failing batch.
    await asyncio.wait_for(run_task, timeout=1.0)

    types = [e["event"] for e in events]
    assert types.count("label-result") == 5, types
    assert types.count("stream-end") == 1, types
    assert types[-1] == "stream-end"
    assert events[-1]["data"]["failed_count"] == 1
    # Every label was attempted, including the three after the failure.
    assert evaluator.calls == 5
    assert set(in_flight.results.keys()) == {f"lbl-{i}" for i in range(5)}

    # The failed item carries a needs_review result naming the reason code...
    refused = in_flight.results["lbl-1"]
    assert refused.disposition == "needs_review"
    assert refused.fields == ()
    assert [t.rule_id for t in refused.audit_trail.per_rule_trace] == [
        "ENGINE.WORKER.UNHANDLED"
    ]
    # ...and a sentence that names the item, for the reviewer to read.
    assert set(in_flight.failures) == {"lbl-1"}
    assert "lbl-1" in in_flight.failures["lbl-1"]
    assert "ValueError" in in_flight.failures["lbl-1"]

    # The snapshot shows it as failed, with the other four unaffected.
    snapshot = in_flight.snapshot()
    by_id = {item.label_id: item for item in snapshot.items}
    assert by_id["lbl-1"].state == ItemState.FAILED
    assert by_id["lbl-1"].failed_reason == in_flight.failures["lbl-1"]
    assert [by_id[f"lbl-{i}"].state for i in (0, 2, 3, 4)] == [ItemState.READY] * 4
