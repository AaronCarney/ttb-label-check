"""InFlightBatch — mutable companion to the frozen BatchInFlightState."""
from collections import deque
from datetime import datetime, timezone

import pytest

from app.batch.state import InFlightBatch
from app.schemas.batch import BatchInFlightState, BatchItem, ItemState


def _stub_item(label_id: str, *, position: int = 0) -> BatchItem:
    return BatchItem(
        label_id=label_id,
        application_ref=f"app-{position:04d}",
        state=ItemState.QUEUED,
        result=None,
        enqueued_at=datetime(2026, 5, 4, 12, 0, position, tzinfo=timezone.utc),
    )


def test_in_flight_batch_constructs_with_items_and_lookahead():
    items = (_stub_item("lbl-0", position=0), _stub_item("lbl-1", position=1))
    in_flight = InFlightBatch(
        batch_id="B-001",
        agent_id="agent-mvp",
        items=items,
        lookahead_k=3,
    )
    assert in_flight.batch_id == "B-001"
    assert in_flight.agent_id == "agent-mvp"
    assert in_flight.items == items
    assert in_flight.current_index == 0
    assert in_flight.lookahead_k == 3
    assert in_flight.results == {}
    assert isinstance(in_flight.recent_dispositions, deque)
    assert in_flight.recent_dispositions.maxlen == 10
    assert isinstance(in_flight.calls, deque)
    assert in_flight.calls.maxlen == 200


def test_in_flight_batch_queue_is_bounded_by_lookahead_plus_one():
    items = tuple(_stub_item(f"lbl-{i}", position=i) for i in range(5))
    in_flight = InFlightBatch(batch_id="B-002", agent_id="a", items=items, lookahead_k=2)
    # maxsize = lookahead_k + 1 = 3
    assert in_flight.queue.maxsize == 3


def test_in_flight_batch_record_result_updates_results_and_advances_index():
    from tests.conftest import _stub_disposition_envelope

    items = (_stub_item("lbl-0", position=0), _stub_item("lbl-1", position=1))
    in_flight = InFlightBatch(batch_id="B-003", agent_id="a", items=items, lookahead_k=3)

    env = _stub_disposition_envelope(0)
    in_flight.record_result("lbl-0", env)

    assert in_flight.results == {"lbl-0": env}
    # current_index advances when a result lands at the cursor position
    assert in_flight.current_index == 1


def test_in_flight_batch_snapshot_returns_frozen_pydantic_state():
    items = (_stub_item("lbl-0", position=0),)
    in_flight = InFlightBatch(batch_id="B-004", agent_id="a", items=items, lookahead_k=3)

    snap = in_flight.snapshot()
    assert isinstance(snap, BatchInFlightState)
    assert snap.batch_id == "B-004"
    assert snap.agent_id == "a"
    assert snap.current_index == 0
    assert snap.lookahead_k == 3
    # Frozen — mutating raises
    with pytest.raises(Exception):  # pydantic.ValidationError
        snap.batch_id = "X"  # type: ignore[misc]


def test_in_flight_batch_does_not_carry_subscriber_state():
    """SSE subscribers live on the per-batch SSEBus stored in
    ``app.state.buses[batch_id]``, not on InFlightBatch. This test pins the
    boundary so a future drift back into the dataclass fails loudly."""
    items = (_stub_item("lbl-0", position=0),)
    in_flight = InFlightBatch(batch_id="B-005", agent_id="a", items=items, lookahead_k=3)
    assert not hasattr(in_flight, "subscribers")
