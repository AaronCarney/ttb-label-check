"""AuditRecorder — assembly and canonical hashing, with no side effects."""
import subprocess
import sys

from app.schemas.application import Application
from app.schemas.audit import AuditRecord
from app.services.audit import AuditRecorder, _canonical_json, _input_hash, _output_hash
from app.services.engine_meta import EvaluationTimeline
from tests.conftest import _stub_label


def _stub_app():
    return Application(application_id="A-001", evaluation_id="EV-001")


def test_canonical_json_is_byte_stable():
    a = {"b": 2, "a": 1, "c": [3, 2, 1]}
    b = {"a": 1, "c": [3, 2, 1], "b": 2}
    assert _canonical_json(a) == _canonical_json(b)


def test_input_hash_is_deterministic():
    h1 = _input_hash(_stub_app(), _stub_label())
    h2 = _input_hash(_stub_app(), _stub_label())
    assert h1 == h2 and len(h1) == 64


def test_input_hash_excludes_evaluation_id():
    """Warm-path invariant: input_hash must be a content fingerprint
    independent of evaluation_id. Otherwise cache-hit envelopes (which patch
    evaluation_id) would carry an input_hash that no longer matches the
    serialized content, breaking tamper-detection re-computation."""
    app1 = Application(application_id="A-001", evaluation_id="EV-1")
    app2 = Application(application_id="A-001", evaluation_id="EV-2")
    label = _stub_label()
    assert _input_hash(app1, label) == _input_hash(app2, label), (
        "input_hash must NOT vary with evaluation_id; same content → same fingerprint"
    )


def test_output_hash_is_deterministic():
    env_dict = {"evaluation_id": "EV-001", "disposition": "pass"}
    assert _output_hash(env_dict) == _output_hash(env_dict)
    assert len(_output_hash(env_dict)) == 64


def test_audit_assemble_returns_record():
    t = EvaluationTimeline(evaluation_id="EV-001", rule_set_version="rs-1.0")
    t.record_rule_done(rule_id="R-001", duration_ms=10, disposition="pass", evidence_ref="ev/R-001")
    t.finish(total_duration_ms=100)
    rec = AuditRecorder().assemble(
        timeline=t, application=_stub_app(), label=_stub_label(),
        envelope_for_hash={"disposition": "pass", "fields": []},
    )
    assert isinstance(rec, AuditRecord)
    assert rec.evaluation_id == "EV-001"
    assert rec.rule_set_version == "rs-1.0"
    assert len(rec.per_rule_trace) == 1
    assert rec.per_rule_trace[0].rule_id == "R-001"
    assert not hasattr(rec.per_rule_trace[0], "duration_ms")  # durations live in metrics


def test_input_hash_byte_stable_across_processes():
    code = """
from app.schemas.application import Application
from app.schemas.label import Label
app = Application(application_id="A-001", evaluation_id="EV-001")
label = Label(label_id="lbl-001", batch_id="B-001", image_bytes=b"fake-png",
              content_type="image/png", face_tag="front")
from app.services.audit import _input_hash
print(_input_hash(app, label))
"""
    r1 = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    r2 = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert r1.returncode == 0 and r2.returncode == 0
    assert r1.stdout.strip() == r2.stdout.strip()
