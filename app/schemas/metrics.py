"""Per-evaluation telemetry: the ``metrics`` block on the disposition envelope,
and the sibling of ``audit_trail``, which keeps audit and telemetry apart.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PerRuleDurationEntry(BaseModel):
    """One per-rule wall-clock duration entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    duration_ms: int


class Metrics(BaseModel):
    """Telemetry block on the disposition envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_duration_ms: int
    per_rule_durations_ms: tuple[PerRuleDurationEntry, ...]
    vision_duration_ms: int
    orchestrator_duration_ms: int
