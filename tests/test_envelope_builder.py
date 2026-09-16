"""Pure envelope assembly — success path + short-circuit."""
from app.schemas.application import Application
from app.schemas.wire.disposition import DispositionEnvelope
from app.services.audit import AuditRecorder
from app.services.engine_meta import EvaluationTimeline
from app.services.envelope_builder import build_short_circuit_envelope, build_success_envelope
from app.services.metrics_builder import MetricsBuilder
from tests.conftest import _stub_label


def _stub_app():
    return Application(application_id="A-001", evaluation_id="EV-001")


def test_build_short_circuit_envelope():
    t = EvaluationTimeline(evaluation_id="EV-001")
    t.finish(total_duration_ms=10)
    env = build_short_circuit_envelope(
        application=_stub_app(), label=_stub_label(), timeline=t,
        reason_code="WARNING.LEGIBILITY.NEEDS_BETTER_PHOTO",
        audit=AuditRecorder().assemble(timeline=t, application=_stub_app(), label=_stub_label(),
                                       envelope_for_hash={"x": 1}),
        metrics=MetricsBuilder().build(t),
    )
    assert isinstance(env, DispositionEnvelope)
    assert env.disposition == "needs_review"
    assert env.evaluation_id == "EV-001"
    rule_ids = {entry.rule_id for entry in env.audit_trail.per_rule_trace}
    # Short-circuit envelope's per_rule_trace surfaces the reason code as a
    # synthetic entry so reviewers see why the engine routed here.
    assert "WARNING.LEGIBILITY.NEEDS_BETTER_PHOTO" in rule_ids


def test_build_success_envelope_minimal():
    t = EvaluationTimeline(evaluation_id="EV-001")
    t.finish(total_duration_ms=10)
    env = build_success_envelope(
        application=_stub_app(), label=_stub_label(), timeline=t,
        disposition="pass", fields=(),
        audit=AuditRecorder().assemble(timeline=t, application=_stub_app(), label=_stub_label(),
                                       envelope_for_hash={"x": 1}),
        metrics=MetricsBuilder().build(t),
    )
    assert env.disposition == "pass"
    assert env.evaluation_id == "EV-001"
    # Empty fields → ("low", 0.0) for disposition_confidence per aggregation.py
    assert env.disposition_confidence.numeric == 0.0
    assert env.disposition_confidence.band == "low"


# FieldFindingWire projection: one wire entry per distinct canonical field,
# with no duplicate field_name slots.
def test_build_field_findings_projects_canonical_seven():
    """For a fixture-01-shaped happy path (one observation + one expected per
    canonical field, one passing ValidationResult per field), the projection
    emits exactly seven FieldFindingWire entries — one per distinct wire slot."""
    from decimal import Decimal

    from app.schemas.expected import BeverageClass, ExpectedValue
    from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
    from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
    from app.services.envelope_builder import build_field_findings

    em = EngineMeta(engine_version="t", rule_pack_version="t", rule_pack="t",
                    started_at_ms=0, elapsed_ms=0)
    canonical = ("brand_name", "class_type", "alcohol_content", "net_contents",
                 "government_warning", "name_and_address", "country_of_origin")
    observations = tuple(
        FieldObservation(
            field_id=fid, beverage_class=BeverageClass.SPIRITS, observed_value=fid,
            evidence=(Evidence(field_id=fid, source=EvidenceSource.OCR,
                               bbox=(0, 0, 10, 10), match_kind=MatchKind.EXACT,
                               confidence=0.95),),
        ) for fid in canonical
    )
    expected = tuple(ExpectedValue(field_id=fid, value=fid) for fid in canonical)
    results = tuple(
        ValidationResult(
            rule_id=f"R-{fid}", cfr_citation="27 CFR §x",
            beverage_class=BeverageClass.SPIRITS,
            outcome=Outcome.PASS, severity=Severity.INFO,
            aggregated_confidence=0.95,
            evidence=(observations[i].evidence[0],),
            engine_meta=em,
        ) for i, fid in enumerate(canonical)
    )
    fields = build_field_findings(results=results, observations=observations,
                                  expected_values=expected)
    assert len(fields) == 7, f"expected 7 wire entries, got {len(fields)}"
    wire_names = {f.field_name for f in fields}
    # Each canonical id maps to a distinct wire slot; the set's length is what
    # proves there are no duplicate slots.
    assert wire_names == {"brand_name", "class_type", "alcohol_content",
                          "net_contents", "warning", "name_address",
                          "country_of_origin"}, (
        f"wire names mismatch: {wire_names}"
    )


def test_build_field_findings_empty_when_no_observations():
    """fixture-04-shaped legibility short-circuit: no observations → projection
    emits zero wire entries (the short-circuit envelope passes fields=())."""
    from app.services.envelope_builder import build_field_findings

    fields = build_field_findings(results=(), observations=(), expected_values=())
    assert fields == ()
