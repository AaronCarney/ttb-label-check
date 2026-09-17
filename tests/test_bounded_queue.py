"""BoundedQueue — typed wrapper around asyncio.Queue(maxsize=k+1).
The producer blocks when the consumer holds, saturating at k+1."""

import asyncio
from datetime import UTC, datetime

import pytest

from app.batch.queue import BoundedQueue
from app.schemas.batch import BatchItem, ItemState


def _stub(idx: int) -> BatchItem:
    return BatchItem(
        label_id=f"lbl-{idx}",
        application_ref=f"app-{idx:04d}",
        state=ItemState.QUEUED,
        result=None,
        enqueued_at=datetime(2026, 5, 4, 12, 0, idx, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_bounded_queue_constructs_with_lookahead_plus_one_maxsize():
    q = BoundedQueue[BatchItem](lookahead_k=3)
    assert q.maxsize == 4
    assert q.qsize() == 0
    assert q.saturated is False


@pytest.mark.asyncio
async def test_bounded_queue_put_get_preserves_fifo_order():
    q = BoundedQueue[BatchItem](lookahead_k=3)
    for i in range(3):
        await q.put(_stub(i))
    out = [await q.get() for _ in range(3)]
    assert [it.label_id for it in out] == ["lbl-0", "lbl-1", "lbl-2"]


@pytest.mark.asyncio
async def test_bounded_queue_saturates_at_maxsize_and_blocks_producer():
    q = BoundedQueue[BatchItem](lookahead_k=2)  # maxsize = 3
    # Fill to capacity
    for i in range(3):
        await q.put(_stub(i))
    assert q.qsize() == 3
    assert q.saturated is True

    # Fourth put blocks — wrap in wait_for(timeout=0.05) and expect TimeoutError
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(q.put(_stub(3)), timeout=0.05)


@pytest.mark.asyncio
async def test_bounded_queue_get_releases_blocked_producer():
    q = BoundedQueue[BatchItem](lookahead_k=1)  # maxsize = 2
    await q.put(_stub(0))
    await q.put(_stub(1))
    assert q.saturated is True

    # Producer task that will block on a 3rd put
    producer_done = asyncio.Event()

    async def producer() -> None:
        await q.put(_stub(2))
        producer_done.set()

    producer_task = asyncio.create_task(producer())
    await asyncio.sleep(0.02)
    assert producer_done.is_set() is False, "producer should be blocked"

    # Drain one — producer unblocks
    await q.get()
    await asyncio.wait_for(producer_done.wait(), timeout=0.5)
    producer_task.cancel()
