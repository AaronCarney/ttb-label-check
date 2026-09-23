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

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    # The answer shown pre-filled: the verdict itself when the check settled
    # it, and which way it leans when it went to review. A reviewer confirms a
    # lean or corrects it; a settled verdict asks nothing of them.
    lean: Literal["pass", "fail"] | None = None

    @model_validator(mode="after")
    def _settled_verdict_is_its_own_lean(self) -> RuleFindingWire:
        if self.disposition != "needs_review":
            self.lean = self.disposition
        elif self.lean is None:
            self.lean = "fail"
        return self


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
    # The check's own answer for the field, shown pre-filled: a mismatch if any
    # of its rules leans that way, because one element that does not match
    # rejects the label, and a match if every rule does. None when no rule
    # checked the field. A reviewer's correction is kept apart, on the audit
    # trail, so this stays what the check found.
    lean: Literal["pass", "fail"] | None = None

    @model_validator(mode="after")
    def _lean_from_rules(self) -> FieldFindingWire:
        if self.rule_findings:
            self.lean = "fail" if any(rf.lean == "fail" for rf in self.rule_findings) else "pass"
        else:
            self.lean = None
        return self


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
    # The label's pre-filled answer. The disposition when that is settled;
    # when it is needs_review, a mismatch if any field or unfinished check
    # leans that way, else a match. Worked out by
    # `app.services.disposition.label_lean` and kept with every correction.
    lean: Literal["pass", "fail"] | None = None
    audit_trail: AuditRecord
    metrics: Metrics

    @model_validator(mode="after")
    def _fill_lean(self) -> DispositionEnvelope:
        if self.lean is None:
            # Imported here because the rule lives with the other disposition
            # rules, and that module imports this one.
            from app.services.disposition import label_lean

            self.lean = label_lean(self)
        return self
