"""Per-LLM/vision-call ring-buffer entry."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


CallStage = Literal[
    "vision.local_ocr",
    "vision.paddleocr",
    "vision.swt",
    "vision.gpt4o_tiebreak",
    "rule.evaluate",
    "orch.brand_disambig",
    "orch.reasoning_enrich",
    "orch.ocr_reconcile",
]


class CallRecord(BaseModel):
    """Shape stored in ``BatchInFlightState.calls`` ring buffer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ts: datetime
    batch_id: str
    label_id: str
    stage: CallStage
    request: dict[str, Any]
    response: dict[str, Any]
    latency_ms: int
    model: str | None = None
    provider: Literal["openai", "local.rapidocr", "local.paddleocr"] | None = None
    prompt_version: str | None = None
    output_hash: str
