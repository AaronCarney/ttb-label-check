"""SSEBus — per-batch async event broker."""
import asyncio

import pytest

from app.api._sse_bus import SSEBus


@pytest.mark.asyncio
async def test_bus_subscribe_returns_unique_queue_per_call():
    bus = SSEBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    assert q1 is not q2
    assert isinstance(q1, asyncio.Queue)
    assert isinstance(q2, asyncio.Queue)
    assert len(bus.subscribers) == 2


@pytest.mark.asyncio
async def test_bus_broadcast_pushes_to_every_subscriber():
    bus = SSEBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    event = {"event": "label-result", "data": {"label_ref": "lbl-0"}}
    bus.broadcast(event)
    assert (await asyncio.wait_for(q1.get(), timeout=0.1)) == event
    assert (await asyncio.wait_for(q2.get(), timeout=0.1)) == event


@pytest.mark.asyncio
async def test_bus_unsubscribe_removes_subscriber():
    bus = SSEBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    bus.unsubscribe(q1)
    assert q1 not in bus.subscribers
    assert q2 in bus.subscribers


@pytest.mark.asyncio
async def test_bus_broadcast_after_unsubscribe_does_not_push_to_dropped():
    bus = SSEBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    bus.unsubscribe(q1)
    bus.broadcast({"event": "x", "data": {}})
    # q1 stays empty
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(q1.get(), timeout=0.05)
    # q2 receives
    assert (await asyncio.wait_for(q2.get(), timeout=0.1))["event"] == "x"


@pytest.mark.asyncio
async def test_bus_broadcast_with_no_subscribers_is_noop():
    bus = SSEBus()
    # Must not raise
    bus.broadcast({"event": "x", "data": {}})


@pytest.mark.asyncio
async def test_bus_unsubscribe_unknown_queue_is_idempotent_noop():
    bus = SSEBus()
    foreign = asyncio.Queue()
    # Must not raise
    bus.unsubscribe(foreign)


@pytest.mark.asyncio
async def test_bus_replays_buffered_events_to_late_subscribers():
    """Reconnect contract: a late subscriber still sees the events it missed."""
    bus = SSEBus()
    bus.broadcast({"event": "label-result", "data": {"i": 0}})
    bus.broadcast({"event": "label-result", "data": {"i": 1}})

    q = bus.subscribe()  # subscribe AFTER broadcasts
    e0 = await asyncio.wait_for(q.get(), timeout=0.1)
    e1 = await asyncio.wait_for(q.get(), timeout=0.1)
    assert e0["data"]["i"] == 0
    assert e1["data"]["i"] == 1


@pytest.mark.asyncio
async def test_bus_iterate_subscriber_yields_events_until_sentinel():
    """Async iterator helper for sse_starlette.EventSourceResponse."""
    bus = SSEBus()
    q = bus.subscribe()
    bus.broadcast({"event": "label-result", "data": {"i": 0}})
    bus.broadcast({"event": "stream-end", "data": {}})

    received: list[dict] = []
    async for evt in bus.iterate(q, terminator_event="stream-end"):
        received.append(evt)
    assert [e["event"] for e in received] == ["label-result", "stream-end"]
    # Subscriber pruned on terminator
    assert q not in bus.subscribers
