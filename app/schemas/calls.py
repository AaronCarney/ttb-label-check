"""The record a reader writes for each call it makes."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


# Every stage a call can be recorded under. A name belongs here only while
# something in this project emits it; a name for work this project does not do
# tells a reviewer the opposite of the truth.
CallStage = Literal[
    # The local reader, `app/vision/local.py`.
    "vision.local_ocr",
    # The cloud reader, `app/vision/cloud.py`. It reads the whole label, so one
    # stage covers every call it makes.
    "vision.cloud_read",
]


class CallRecord(BaseModel):
    """One recorded reader call. Entries live in the process-wide ring
    buffer the reader holds (``app/logging/ring_buffer.py``), and each
    carries the batch and label it belongs to."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ts: datetime
    batch_id: str
    label_id: str
    stage: CallStage
    request: dict[str, Any]
    response: dict[str, Any]
    latency_ms: int
    model: str | None = None
    provider: Literal["openai", "local.rapidocr"] | None = None
    prompt_version: str | None = None
    output_hash: str
