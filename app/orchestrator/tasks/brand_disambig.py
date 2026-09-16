"""Brand-disambig task schema + adapter."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.refined import Refined, TaskSlice


@dataclass(frozen=True)
class BrandDisambigInput:
    """Input shape for brand-disambig calls."""

    rule_id: str
    applicant_brand: str
    candidate_matches: tuple[str, ...]


class BrandDisambigResult(BaseModel):
    """Pydantic v2 strict-mode output schema. No `pass`/`fail` field: the model
    does not decide an outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["match", "needs_review"]
    justification: str


def to_input(rule_id: str, applicant_brand: str, candidates: list[str]) -> BrandDisambigInput:
    return BrandDisambigInput(
        rule_id=rule_id,
        applicant_brand=applicant_brand,
        candidate_matches=tuple(candidates),
    )


def apply_to_refined(refined: Refined, *, rule_id: str, result: BrandDisambigResult) -> Refined:
    slice_ = TaskSlice(
        task="brand_disambig",
        rule_id=rule_id,
        payload=result.model_dump(),
    )
    return refined.model_copy(update={"tasks": refined.tasks + (slice_,)})
