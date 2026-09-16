"""SessionCache — bounded LRU keyed by canonical input hash."""
import pytest

from app.schemas.application import Application
from app.schemas.audit import AuditRecord
from app.schemas.label import Dimensions, Label
from app.schemas.metrics import Metrics
from app.schemas.wire.disposition import ConfidenceBand, DispositionEnvelope
from app.services.cache import SessionCache


def _stub_envelope(eid="EV-001"):
    from datetime import datetime, timezone
    return DispositionEnvelope(
        evaluation_id=eid, label_ref="lbl", disposition="pass",
        disposition_confidence=ConfidenceBand(band="high", numeric=1.0),
        fields=(),
        audit_trail=AuditRecord(
            evaluation_id=eid, rule_set_version="rs",
            input_hash="0" * 64, output_hash="0" * 64,
            started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc),
            per_rule_trace=(),
        ),
        metrics=Metrics(total_duration_ms=0, per_rule_durations_ms=(),
                        vision_duration_ms=0, orchestrator_duration_ms=0),
    )


def test_cache_get_miss_returns_none():
    c = SessionCache(maxsize=2)
    assert c.get("nope") is None


def test_cache_put_then_get():
    c = SessionCache(maxsize=2)
    env = _stub_envelope()
    c.put("k1", env)
    assert c.get("k1") == env


def test_cache_evicts_lru_at_maxsize():
    c = SessionCache(maxsize=2)
    e1 = _stub_envelope("EV-1")
    e2 = _stub_envelope("EV-2")
    e3 = _stub_envelope("EV-3")
    c.put("k1", e1)
    c.put("k2", e2)
    c.put("k3", e3)  # evicts k1 (LRU)
    assert c.get("k1") is None
    assert c.get("k2") == e2
    assert c.get("k3") == e3


def test_cache_get_promotes_to_most_recent():
    c = SessionCache(maxsize=2)
    e1 = _stub_envelope("EV-1")
    e2 = _stub_envelope("EV-2")
    e3 = _stub_envelope("EV-3")
    c.put("k1", e1)
    c.put("k2", e2)
    c.get("k1")            # promote k1
    c.put("k3", e3)        # should evict k2 now (LRU)
    assert c.get("k1") == e1
    assert c.get("k2") is None


def test_cache_clear_removes_all():
    c = SessionCache(maxsize=2)
    c.put("k1", _stub_envelope())
    c.clear()
    assert c.get("k1") is None
    assert len(c) == 0
