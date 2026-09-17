"""MetricsBuilder — pure assembly of the telemetry block from EvaluationTimeline."""

from __future__ import annotations

from app.schemas.metrics import Metrics, PerRuleDurationEntry
from app.services.engine_meta import EvaluationTimeline


class MetricsBuilder:
    def build(self, timeline: EvaluationTimeline) -> Metrics:
        per_rule = tuple(
            PerRuleDurationEntry(rule_id=rid, duration_ms=ms)
            for rid, ms in timeline.per_rule_durations.items()
        )
        return Metrics(
            total_duration_ms=timeline.total_duration_ms,
            per_rule_durations_ms=per_rule,
            vision_duration_ms=timeline.vision_duration_ms,
        )
