"""Audit and metrics are separate blocks built from one timeline: per-rule
durations belong to the metrics block, never to the audit trail."""

from app.schemas.application import Application
from app.services.audit import AuditRecorder
from app.services.engine_meta import EvaluationTimeline
from app.services.metrics_builder import MetricsBuilder
from tests.conftest import _stub_label


def test_split_no_duration_in_audit_per_rule_trace():
    t = EvaluationTimeline(evaluation_id="EV-001")
    t.record_rule_done(rule_id="R-001", duration_ms=10, disposition="pass", evidence_ref="r1")
    t.finish(total_duration_ms=20)

    audit = AuditRecorder().assemble(
        timeline=t,
        application=Application(application_id="A", evaluation_id="EV-001"),
        label=_stub_label(),
        envelope_for_hash={"x": 1},
    )
    metrics = MetricsBuilder().build(t)

    assert audit.per_rule_trace[0].rule_id == "R-001"
    assert not hasattr(audit.per_rule_trace[0], "duration_ms")
    assert metrics.per_rule_durations_ms[0].duration_ms == 10
