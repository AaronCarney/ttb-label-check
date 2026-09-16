"""In-memory mutable companion to the frozen ``BatchInFlightState``.

Owns the per-batch state machinery that does not belong inside frozen Pydantic:
the per-batch ``asyncio.Queue`` (intake → worker), the SSE subscriber set, the
``recent_dispositions`` sliding window, the per-label ``results`` map, and the
``current_index`` cursor.

Calls the readers make are not held here. One reader serves the process
(``app/deps.py``) and records into the one ring buffer it holds, which outlives
the request; every ``CallRecord`` carries its own ``batch_id`` and ``label_id``,
so a per-batch view of those calls is a filter over that buffer rather than a
second copy of it.

Lives in ``app.state.batches: dict[str, InFlightBatch]`` — process-local, with
nothing about a submission persisted. Lifespan teardown evicts.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from app.batch.queue import BoundedQueue
from app.schemas.batch import BatchInFlightState, BatchItem
from app.schemas.wire.disposition import DispositionEnvelope


@dataclass
class InFlightBatch:
    """Mutable per-batch state. Owned by the call frame of the worker and
    surfaced via ``app.state.batches``.

    SSE subscribers are NOT tracked here — they live on the per-batch
    ``SSEBus``, which is stored separately in ``app.state.buses[batch_id]``
    so the substitutability seam (BoundedQueue + SSEBus) stays uncoupled from
    in-flight per-batch state."""

    batch_id: str
    agent_id: str
    items: tuple[BatchItem, ...]
    lookahead_k: int = 3
    current_index: int = 0
    results: dict[str, DispositionEnvelope] = field(default_factory=dict)
    recent_dispositions: deque = field(
        default_factory=lambda: deque(maxlen=10)
    )
    queue: "BoundedQueue[BatchItem]" = field(init=False)

    def __post_init__(self) -> None:
        # maxsize = k+1 (in BoundedQueue) is the structural enforcement of
        # pull-based demand — the producer's `await queue.put(item)` blocks
        # when the consumer holds. Going through BoundedQueue keeps the queue
        # swappable for another bounded primitive (a Kafka consumer group, or
        # RabbitMQ with prefetch=1) without touching this class.
        self.queue = BoundedQueue(lookahead_k=self.lookahead_k)

    def record_result(self, label_id: str, envelope: DispositionEnvelope) -> None:
        """Record a per-label result. Advances ``current_index`` if the result
        lands at the cursor position (so the next reviewer-pull starts there)."""
        self.results[label_id] = envelope
        # Advance cursor while the next item has a result
        while self.current_index < len(self.items):
            cur = self.items[self.current_index]
            if cur.label_id in self.results:
                self.current_index += 1
            else:
                break

    def snapshot(self) -> BatchInFlightState:
        """Build a frozen serializable snapshot for ``GET /batches/{batch_id}``.

        Per-item ``state`` and ``result`` are reconstructed from the runtime
        state — the original ``items`` tuple carries the queued state at
        submission time."""
        rebuilt: list[BatchItem] = []
        for idx, item in enumerate(self.items):
            envelope = self.results.get(item.label_id)
            new_state = item.state
            new_result: dict | None = None
            if envelope is not None:
                # The item completed evaluation. Mark it as `ready` (delivered
                # to the consumer when the SSE event was emitted; transitions
                # to `presented`/`reviewed`/`disposed` are reviewer-driven and
                # surfaced as state transitions in later iterations).
                from app.schemas.batch import ItemState

                new_state = ItemState.READY
                new_result = envelope.model_dump(mode="json")
            rebuilt.append(item.model_copy(update={"state": new_state, "result": new_result}))
        return BatchInFlightState(
            batch_id=self.batch_id,
            agent_id=self.agent_id,
            items=tuple(rebuilt),
            current_index=self.current_index,
            lookahead_k=self.lookahead_k,
        )
