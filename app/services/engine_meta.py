"""EvaluationTimeline — per-evaluation accumulator for timings and outcomes.

Both ``AuditRecorder.assemble`` and ``MetricsBuilder.build`` consume the same
``EvaluationTimeline`` instance constructed and mutated by ``Evaluator.evaluate``.
This is the ONE source of truth for per-evaluation timing + outcome data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class EngineFailure:
    """One typed engine-failure event captured during evaluation."""

    reason_code: str
    message: str
    exception_class: str


@dataclass
class EvaluationTimeline:
    """Mutable per-evaluation accumulator. Owned by the call frame of
    ``Evaluator.evaluate`` and consumed exactly twice (audit + metrics)."""

    evaluation_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    total_duration_ms: int = 0
    vision_duration_ms: int = 0
    per_rule_durations: dict[str, int] = field(default_factory=dict)
    per_rule_dispositions: dict[str, str] = field(default_factory=dict)
    per_rule_evidence_refs: dict[str, str] = field(default_factory=dict)
    # The trace entry's name, for a row stored under a key other than its
    # name. See `record_rule_done`.
    per_rule_ids: dict[str, str] = field(default_factory=dict)
    rule_set_version: str = "unknown"
    model_version: str | None = None
    prompt_version: str | None = None
    failures: list[EngineFailure] = field(default_factory=list)

    def record_vision_done(self, duration_ms: int) -> None:
        self.vision_duration_ms = duration_ms

    def record_rule_done(
        self,
        *,
        rule_id: str,
        duration_ms: int,
        disposition: str,
        evidence_ref: str,
        row_key: str | None = None,
    ) -> None:
        """Record one trace row. Recording the same row again rewrites it.

        A row is stored under its name unless `row_key` says otherwise. A
        reason-code row is named by its code, and several rules may report the
        same code, so it is stored under a key naming its rule; stored under
        its name, each such rule's row would overwrite the one before.
        """
        key = row_key or rule_id
        self.per_rule_durations[key] = duration_ms
        self.per_rule_dispositions[key] = disposition
        self.per_rule_evidence_refs[key] = evidence_ref
        if key != rule_id:
            self.per_rule_ids[key] = rule_id

    def record_failure(self, *, reason_code: str, message: str, exception_class: str) -> None:
        self.failures.append(
            EngineFailure(reason_code=reason_code, message=message, exception_class=exception_class)
        )

    def finish(self, total_duration_ms: int) -> None:
        self.total_duration_ms = total_duration_ms
        self.completed_at = datetime.now(UTC)
