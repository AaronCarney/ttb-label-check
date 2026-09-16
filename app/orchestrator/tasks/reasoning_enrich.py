"""Reasoning-enrich task schema + adapter."""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from app.schemas.refined import Refined, TaskSlice


@dataclass(frozen=True)
class ReasoningEnrichInput:
    rule_id: str
    template_text: str


class EnrichedReasoning(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plain_language: str
    citation_anchor: str


def apply_to_refined(refined: Refined, *, rule_id: str, result: EnrichedReasoning) -> Refined:
    slice_ = TaskSlice(
        task="reasoning_enrich",
        rule_id=rule_id,
        payload=result.model_dump(),
    )
    return refined.model_copy(update={"tasks": refined.tasks + (slice_,)})
