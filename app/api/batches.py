"""POST /batches, GET /batches/{batch_id}/stream, GET /batches/{batch_id}."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.api import limits
from app.api._sse_bus import SSEBus
from app.batch.anomaly import AnomalyDetector
from app.batch.state import InFlightBatch
from app.batch.worker import BatchWorker
from app.config import Settings
from app.schemas.batch import BatchItem, ItemState
from app.schemas.wire.batch import BatchEnvelope

router = APIRouter()
_logger = logging.getLogger("app.api.batches")


def _get_settings() -> Settings:
    """Module-private Settings factory, as in app/api/healthz.py and
    app/api/labels.py — `app/deps.py` exposes no `get_settings` by design.
    Tests override via FastAPI's dependency_overrides[]."""
    return Settings()


def _build_in_flight_from_envelope(env: BatchEnvelope, *, lookahead_k: int) -> InFlightBatch:
    from datetime import datetime

    now = datetime.now(UTC)
    items = tuple(
        BatchItem(
            label_id=ref.label_ref,
            application_ref=ref.application_ref,
            state=ItemState.QUEUED,
            result=None,
            enqueued_at=now,
        )
        for ref in env.items
    )
    return InFlightBatch(
        batch_id=env.batch_id,
        agent_id=env.agent_id,
        items=items,
        lookahead_k=lookahead_k,
    )


def _resolve_lookahead_k(settings: Settings) -> int:
    """LOOKAHEAD_K resolved through Settings, the one place env vars are read."""
    return max(1, settings.lookahead_k)


@router.post("/batches", status_code=202)
async def post_batches(
    envelope: BatchEnvelope,
    request: Request,
    settings: Settings = Depends(_get_settings),
) -> dict[str, str]:
    """Spawn a worker and return the batch_id."""
    if len(envelope.items) > limits.MAX_BATCH_FILES:
        # The same fairness limit the browser's bulk upload enforces. This route
        # takes references rather than files, so no byte cap applies to it, and
        # the item count is the only thing bounding the work one request asks
        # for.
        raise HTTPException(
            status_code=413,
            detail=limits.too_many_files_message(
                len(envelope.items), limits.MAX_BATCH_FILES
            ),
        )

    if envelope.batch_id in request.app.state.batches:
        _logger.warning(
            f"batch_submit_conflict batch_id={envelope.batch_id} agent_id={envelope.agent_id} items={len(envelope.items)}",
            extra={"batch_id": envelope.batch_id, "reason_code": "ENGINE.BATCH.CONFLICT"},
        )
        raise HTTPException(status_code=409, detail=f"batch_id {envelope.batch_id} already in flight")

    lookahead_k = _resolve_lookahead_k(settings)
    in_flight = _build_in_flight_from_envelope(envelope, lookahead_k=lookahead_k)
    bus = SSEBus()
    request.app.state.batches[envelope.batch_id] = in_flight
    request.app.state.buses[envelope.batch_id] = bus

    # Build the evaluator via the shared factory; tests monkeypatch this.
    from app.deps import build_evaluator
    evaluator = build_evaluator(settings)

    worker = BatchWorker(
        in_flight=in_flight,
        evaluator=evaluator,
        anomaly=AnomalyDetector(),
        bus=bus,
    )
    asyncio.create_task(worker.run())
    _logger.info(
        f"batch_accepted batch_id={envelope.batch_id} agent_id={envelope.agent_id} items={len(envelope.items)} lookahead_k={lookahead_k}",
        extra={"batch_id": envelope.batch_id, "reason_code": "ENGINE.OK.NONE"},
    )
    return {"batch_id": envelope.batch_id}


@router.get("/batches/{batch_id}")
async def get_batch_snapshot(batch_id: str, request: Request) -> dict[str, Any]:
    in_flight = request.app.state.batches.get(batch_id)
    if in_flight is None:
        _logger.warning(
            f"batch_snapshot_not_found batch_id={batch_id}",
            extra={"batch_id": batch_id, "reason_code": "ENGINE.BATCH.NOT_FOUND"},
        )
        raise HTTPException(status_code=404, detail=f"batch_id {batch_id} not found")
    return in_flight.snapshot().model_dump(mode="json")


@router.get("/batches/{batch_id}/stream")
async def get_batch_stream(batch_id: str, request: Request):
    in_flight = request.app.state.batches.get(batch_id)
    if in_flight is None:
        _logger.warning(
            f"batch_stream_not_found batch_id={batch_id}",
            extra={"batch_id": batch_id, "reason_code": "ENGINE.BATCH.NOT_FOUND"},
        )
        raise HTTPException(status_code=404, detail=f"batch_id {batch_id} not found")
    bus: SSEBus | None = request.app.state.buses.get(batch_id)
    if bus is None:
        _logger.warning(
            f"batch_stream_bus_missing batch_id={batch_id}",
            extra={"batch_id": batch_id, "reason_code": "ENGINE.BATCH.NOT_FOUND"},
        )
        raise HTTPException(status_code=404, detail=f"batch_id {batch_id} stream not registered")
    sub = bus.subscribe()
    replay_count = sub.qsize()
    _logger.info(
        f"batch_stream_subscribed batch_id={batch_id} replay={replay_count} subscribers={len(bus.subscribers)}",
        extra={"batch_id": batch_id, "reason_code": "ENGINE.OK.NONE"},
    )

    async def _event_generator():
        events_yielded = 0
        terminated = False
        try:
            async for evt in bus.iterate(sub, terminator_event="stream-end"):
                events_yielded += 1
                if evt.get("event") == "stream-end":
                    terminated = True
                # sse_starlette str()s non-string data → Python repr breaks
                # JSON.parse on the client. Serialize dicts ourselves.
                data = evt["data"]
                if not isinstance(data, (str, bytes)):
                    data = json.dumps(data, default=str)
                yield {"event": evt["event"], "data": data}
        finally:
            bus.unsubscribe(sub)
            _logger.info(
                f"batch_stream_closed batch_id={batch_id} events={events_yielded} terminated={terminated}",
                extra={"batch_id": batch_id, "reason_code": "ENGINE.OK.NONE"},
            )

    return EventSourceResponse(_event_generator())
