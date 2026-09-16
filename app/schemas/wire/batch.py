"""The batch envelope: what an agent submits for a batch of labels."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BatchItemRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label_ref: str
    application_ref: str


class BatchEnvelope(BaseModel):
    """The batch envelope. ``agent_id`` is structurally present, but the app
    serves one agent at a time."""

    model_config = ConfigDict(extra="forbid")

    batch_id: str
    agent_id: str
    submitted_at: datetime
    items: tuple[BatchItemRef, ...]
