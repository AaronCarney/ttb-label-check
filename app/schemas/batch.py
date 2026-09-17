"""Batch-processor session-scoped state."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ItemState(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    PRESENTED = "presented"
    REVIEWED = "reviewed"
    DISPOSED = "disposed"
    FAILED = "failed"


class BatchItem(BaseModel):
    """Per-label state machine entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label_id: str
    application_ref: str
    state: ItemState
    result: dict[str, Any] | None = None
    enqueued_at: datetime
    failed_reason: str | None = None


class BatchInFlightState(BaseModel):
    """Session-scoped state for an in-progress batch.

    The actual ``recent_dispositions`` deque is an in-memory mutable structure
    held outside the Pydantic envelope, on ``InFlightBatch``; this model
    captures only the serializable subset. Reader calls are not per-batch state
    at all — they go to the one ring buffer the process-wide reader holds.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    batch_id: str
    agent_id: str
    items: tuple[BatchItem, ...]
    current_index: int = 0
    lookahead_k: int = Field(default=3, ge=1)
