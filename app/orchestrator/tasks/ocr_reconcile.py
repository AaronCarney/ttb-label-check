"""OCR-reconcile task schema + adapter."""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from app.schemas.refined import Refined, TaskSlice


@dataclass(frozen=True)
class OcrReconcileInput:
    rule_id: str
    field_id: str
    candidate_reads: tuple[str, ...]


class OcrReconcileResult(BaseModel):
    """winner=None ⇒ orchestrator abstains. Application Service routes to needs_review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    winner: str | None = None
    reasoning: str


def apply_to_refined(refined: Refined, *, rule_id: str, result: OcrReconcileResult) -> Refined:
    slice_ = TaskSlice(
        task="ocr_reconcile",
        rule_id=rule_id,
        payload=result.model_dump(),
    )
    return refined.model_copy(update={"tasks": refined.tasks + (slice_,)})
