"""The disposition-output envelope: what the app reports for one label. Audit
and telemetry are carried in separate blocks.

**Confidence aggregation.** ``disposition_confidence.numeric`` is the **min**
over per-field ``field_confidence.numeric``, so a result is only as confident as
its least confident field. This module ships the type that carries the values;
the aggregation runs in ``app/services/aggregation.py`` during disposition
assembly, not at parse time.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.audit import AuditRecord
from app.schemas.metrics import Metrics

Band = Literal["high", "medium", "low"]
Disposition = Literal["pass", "fail", "needs_review"]


class ConfidenceBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    band: Band
    numeric: float = Field(ge=0.0, le=1.0)


class FieldEvidenceWire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bbox: tuple[int, int, int, int]
    crop_ref: str
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    # Which photograph of the label this was read from ("front", "back", …),
    # or empty when the reading did not record one. A label is filed as
    # several photographs and its mandatory elements are spread across them,
    # so a finding that cannot name its face is a finding the reviewer cannot
    # check. Empty rather than a default of "front": a warning finding is
    # precisely the one that is usually not on the front, and a wrong face is
    # worse than no face.
    face_tag: str = ""


class RuleFindingWire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    cfr_citation: str
    disposition: Literal["pass", "fail", "needs_review"]
    reason_code: str
    plain_language_explanation: str
    # Which of the application's values this rule matched, when it was not the
    # one shown as expected. Empty otherwise. Without it a card reads
    # "Expected FABIO SIGNORELLI / Found Rossastro / PASS", which contradicts
    # itself: the rule matched the fanciful name the same application declares.
    matched_value: str = ""


class AISuggestionWire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present: bool
    task: (
        Literal[
            "brand_borderline",
            "reasoning_enrichment",
            "ocr_reconciliation",
        ]
        | None
    ) = None
    text: str | None = None
    model_disposition: Literal["pass", "needs_review"] | None = None


class FieldFindingWire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: Literal[
        "brand_name",
        "class_type",
        "alcohol_content",
        "net_contents",
        "warning",
        "name_address",
        "country_of_origin",
    ]
    extracted_value: str
    expected_value: str
    evidence: FieldEvidenceWire
    rule_findings: tuple[RuleFindingWire, ...]
    ai_suggestion: AISuggestionWire
    field_confidence: ConfidenceBand


class DispositionEnvelope(BaseModel):
    """The outbound envelope for one label.

    ``audit_trail.per_rule_trace[]`` does NOT carry ``duration_ms``; per-rule
    durations live in the sibling ``metrics`` block.
    """

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    label_ref: str
    disposition: Disposition
    disposition_confidence: ConfidenceBand
    fields: tuple[FieldFindingWire, ...]
    audit_trail: AuditRecord
    metrics: Metrics
