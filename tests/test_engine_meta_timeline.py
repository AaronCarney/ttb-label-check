"""EvaluationTimeline — the per-evaluation accumulator both the audit trail and
the metrics block are built from."""
import pytest

from app.services.engine_meta import EvaluationTimeline, EngineFailure


def test_timeline_constructs_with_evaluation_id():
    t = EvaluationTimeline(evaluation_id="EV-001")
    assert t.evaluation_id == "EV-001"
    assert t.vision_duration_ms == 0
    assert t.per_rule_durations == {}
    assert t.failures == []


def test_timeline_records_vision_duration():
    t = EvaluationTimeline(evaluation_id="EV-001")
    t.record_vision_done(123)
    assert t.vision_duration_ms == 123


def test_timeline_records_per_rule_outcome():
    t = EvaluationTimeline(evaluation_id="EV-001")
    t.record_rule_done(rule_id="R-001", duration_ms=42, disposition="pass", evidence_ref="ev/R-001")
    assert t.per_rule_durations == {"R-001": 42}
    assert t.per_rule_dispositions == {"R-001": "pass"}
    assert t.per_rule_evidence_refs == {"R-001": "ev/R-001"}


def test_timeline_records_engine_failure():
    t = EvaluationTimeline(evaluation_id="EV-001")
    t.record_failure(reason_code="ENGINE.SLA.RULE_TIMEOUT", message="slow", exception_class="TimeoutError")
    assert len(t.failures) == 1
    f = t.failures[0]
    assert f.reason_code == "ENGINE.SLA.RULE_TIMEOUT"
    assert f.message == "slow"
    assert f.exception_class == "TimeoutError"


def test_timeline_finish_records_completed_at():
    from datetime import datetime, timezone

    t = EvaluationTimeline(evaluation_id="EV-001")
    assert t.completed_at is None
    t.finish(total_duration_ms=500)
    assert t.total_duration_ms == 500
    assert isinstance(t.completed_at, datetime)
    assert t.completed_at.tzinfo == timezone.utc


def test_engine_failure_is_frozen():
    import dataclasses

    f = EngineFailure(reason_code="ENGINE.RULE.UNKNOWN", message="x", exception_class="ValueError")
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.reason_code = "X"  # type: ignore[misc]
