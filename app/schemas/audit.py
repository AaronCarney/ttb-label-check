"""In-memory audit-trail models.

Audit and telemetry are kept apart: per-rule durations live in
``app.schemas.metrics``, and ``audit_trail.per_rule_trace[]`` carries only
audit-relevant fields (rule_id, disposition, evidence_ref).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class PerRuleTraceEntry(BaseModel):
    """One entry in the audit-trail per-rule trace.

    Audit-relevant fields only — no telemetry.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    disposition: Literal["pass", "fail", "needs_review", "not_applicable"]
    evidence_ref: str


class OverrideEntry(BaseModel):
    """Reviewer override recorded in the audit trail."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_name: str | None = None
    original_disposition: Literal["pass", "fail", "needs_review"]
    applied_disposition: Literal["pass", "fail", "needs_review"]
    reason_code: str
    justification_text: str | None = None
    reviewer_id: str
    timestamp: datetime


class AuditRecord(BaseModel):
    """Audit-trail object carried on the disposition envelope as ``audit_trail``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evaluation_id: str
    rule_set_version: str
    model_version: str | None = None
    prompt_version: str | None = None
    input_hash: str
    output_hash: str
    started_at: datetime
    completed_at: datetime
    per_rule_trace: tuple[PerRuleTraceEntry, ...]
    overrides: tuple[OverrideEntry, ...] = ()
