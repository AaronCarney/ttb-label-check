from app.schemas.metrics import Metrics
from app.services.engine_meta import EvaluationTimeline
from app.services.metrics_builder import MetricsBuilder


def test_build_returns_metrics():
    t = EvaluationTimeline(evaluation_id="EV-001")
    t.record_vision_done(100)
    t.record_orchestrator_done(200)
    t.record_rule_done(rule_id="R-001", duration_ms=10, disposition="pass", evidence_ref="r1")
    t.record_rule_done(rule_id="R-002", duration_ms=20, disposition="fail", evidence_ref="r2")
    t.finish(total_duration_ms=400)

    m = MetricsBuilder().build(t)
    assert isinstance(m, Metrics)
    assert m.total_duration_ms == 400
    assert m.vision_duration_ms == 100
    assert m.orchestrator_duration_ms == 200
    assert {(e.rule_id, e.duration_ms) for e in m.per_rule_durations_ms} == {
        ("R-001", 10), ("R-002", 20),
    }


def test_build_with_empty_per_rule():
    t = EvaluationTimeline(evaluation_id="EV-002")
    t.finish(total_duration_ms=1)
    m = MetricsBuilder().build(t)
    assert m.per_rule_durations_ms == ()


def test_build_is_pure_no_side_effects():
    t = EvaluationTimeline(evaluation_id="EV-003")
    t.record_vision_done(50)
    t.finish(total_duration_ms=60)
    builder = MetricsBuilder()
    assert builder.build(t) == builder.build(t)
