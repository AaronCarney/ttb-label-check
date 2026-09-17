"""Vision-extractor output models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.expected import BeverageClass

BBox = tuple[int, int, int, int]


class EvidenceSource(StrEnum):
    OCR = "ocr"
    LAYOUT = "layout"
    CLASSIFIER = "classifier"
    DERIVED = "derived"
    METADATA = "metadata"


class MatchKind(StrEnum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    FUZZY = "fuzzy"
    HASH = "hash"
    NUMERIC_BAND = "numeric_band"
    LOOKUP = "lookup"
    REGEX = "regex"
    LAYOUT = "layout"
    NONE = "none"


class Evidence(BaseModel):
    """A single piece of evidence supporting (or contradicting) a rule outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: str
    source: EvidenceSource
    page_id: str | None = None
    panel: str | None = None
    image_uri: str | None = None
    bbox: BBox | None = None
    extracted_text: str | None = None
    normalized_text: str | None = None
    matched_against_value: str | None = None
    match_kind: MatchKind
    match_score: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None = None


class FieldObservation(BaseModel):
    """What the Vision Extractor produces for one extracted field on one label."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: str
    beverage_class: BeverageClass
    observed_value: Any | None = None
    evidence: tuple[Evidence, ...]
    timestamp_ms: int | None = None
    upstream_meta: dict[str, Any] = Field(default_factory=dict)
