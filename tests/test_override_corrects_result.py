"""A reviewer's correction to one field moves the label's result with it.

A result stands until the reviewer says it is wrong. When they do, the field's
card and the label's overall result both follow the correction, by the same rule
the engine used: one failed field fails the label (docs/decisions.md#0064).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas.application import Application
from app.schemas.audit import AuditRecord, OverrideEntry, PerRuleTraceEntry
from app.schemas.expected import BeverageClass
from app.schemas.metrics import Metrics
from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
from app.schemas.wire.disposition import ConfidenceBand, DispositionEnvelope
from app.services import disposition as disposition_module
from app.services.disposition import disposition_after_overrides, field_disposition
from app.services.evaluator import Evaluator
from app.vision.quality import QualityReport
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_field_finding, _stub_label

_NOW = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)


def _envelope(
    fields: dict[str, str], *, disposition: str, extra_trace: tuple[PerRuleTraceEntry, ...] = ()
) -> DispositionEnvelope:
    """An envelope shaped as the engine builds one: a trace row per rule, and a
    second row under the rule's reason code when it did not pass."""
    trace: list[PerRuleTraceEntry] = []
    for name, verdict in fields.items():
        rule_id = f"R-{name}"
        trace.append(
            PerRuleTraceEntry(rule_id=rule_id, disposition=verdict, evidence_ref=f"vr/{rule_id}")
        )
        if verdict != "pass":
            trace.append(
                PerRuleTraceEntry(
                    rule_id=f"{name.upper()}.MATCH.CODE",
                    disposition=verdict,
                    evidence_ref=f"reason_code/{rule_id}",
                )
            )
    return DispositionEnvelope(
        evaluation_id="EV-C",
        label_ref="lbl-c",
        disposition=disposition,  # type: ignore[arg-type]
        disposition_confidence=ConfidenceBand(band="high", numeric=0.9),
        fields=tuple(_stub_field_finding(n, f"R-{n}", v) for n, v in fields.items()),
        audit_trail=AuditRecord(
            evaluation_id="EV-C",
            rule_set_version="t",
            input_hash="0" * 64,
            output_hash="0" * 64,
            started_at=_NOW,
            completed_at=_NOW,
            per_rule_trace=(*trace, *extra_trace),
        ),
        metrics=Metrics(total_duration_ms=1, per_rule_durations_ms=(), vision_duration_ms=1),
    )


def _corrected(
    env: DispositionEnvelope, *corrections: tuple[str | None, str]
) -> DispositionEnvelope:
    entries = tuple(
        OverrideEntry(
            field_name=name,
            original_disposition="pass",
            applied_disposition=applied,  # type: ignore[arg-type]
            reason_code="REVIEWER.CORRECTION.PASS",
            reviewer_id="session-t",
            timestamp=_NOW,
        )
        for name, applied in corrections
    )
    return env.model_copy(
        update={"audit_trail": env.audit_trail.model_copy(update={"overrides": entries})}
    )


# --------------------------------------------------------------------------
# The rule
# --------------------------------------------------------------------------


def test_with_no_correction_the_engines_answer_stands() -> None:
    env = _envelope({"brand_name": "fail"}, disposition="fail")
    assert disposition_after_overrides(env) == "fail"


def test_correcting_the_only_mismatch_to_a_match_passes_the_label() -> None:
    env = _envelope({"brand_name": "fail", "alcohol_content": "pass"}, disposition="fail")
    assert disposition_after_overrides(_corrected(env, ("brand_name", "pass"))) == "pass"


def test_one_field_corrected_to_a_mismatch_fails_the_label() -> None:
    env = _envelope({"brand_name": "pass", "alcohol_content": "pass"}, disposition="pass")
    assert disposition_after_overrides(_corrected(env, ("alcohol_content", "fail"))) == "fail"


def test_another_field_still_to_review_keeps_the_label_with_a_reviewer() -> None:
    env = _envelope({"brand_name": "fail", "warning": "needs_review"}, disposition="fail")
    assert disposition_after_overrides(_corrected(env, ("brand_name", "pass"))) == "needs_review"


def test_the_latest_correction_to_a_field_is_its_answer() -> None:
    env = _envelope({"brand_name": "pass"}, disposition="pass")
    corrected = _corrected(env, ("brand_name", "fail"), ("brand_name", "pass"))
    assert disposition_after_overrides(corrected) == "pass"
    assert field_disposition(corrected, "brand_name") == "pass"


def test_a_stopped_check_is_not_passed_by_correcting_its_fields() -> None:
    stopped = PerRuleTraceEntry(
        rule_id="ENGINE.EVALUATION.TIMEOUT",
        disposition="needs_review",
        evidence_ref="engine_failure/x",
    )
    env = _envelope({"brand_name": "fail"}, disposition="needs_review", extra_trace=(stopped,))
    assert disposition_after_overrides(_corrected(env, ("brand_name", "pass"))) == "needs_review"


def test_a_correction_to_the_whole_label_stands_over_the_fields() -> None:
    env = _envelope({"brand_name": "pass"}, disposition="pass")
    corrected = _corrected(env, (None, "needs_review"), ("brand_name", "pass"))
    assert disposition_after_overrides(corrected) == "needs_review"


def test_a_field_no_rule_checked_has_no_result_to_correct() -> None:
    env = _envelope({"brand_name": "pass"}, disposition="pass")
    unchecked = env.fields[0].model_copy(update={"field_name": "net_contents", "rule_findings": ()})
    env = env.model_copy(update={"fields": (*env.fields, unchecked)})
    assert field_disposition(env, "net_contents") is None
    assert field_disposition(env, "country_of_origin") is None


# --------------------------------------------------------------------------
# The trace the rule reads agrees with the engine's own answer
# --------------------------------------------------------------------------


def _em() -> EngineMeta:
    return EngineMeta(
        engine_version="t", rule_pack_version="t", rule_pack="t", started_at_ms=0, elapsed_ms=0
    )


def _vr(i: int, outcome: Outcome, severity: Severity) -> ValidationResult:
    return ValidationResult(
        rule_id=f"R-{i}",
        cfr_citation="27 CFR §x",
        beverage_class=BeverageClass.SPIRITS,
        outcome=outcome,
        severity=severity,
        reason_code=None if outcome == Outcome.PASS else "BRAND.NAME.NEEDS_REVIEW",
        aggregated_confidence=0.9,
        engine_meta=_em(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "findings",
    [
        ((Outcome.PASS, Severity.INFO), (Outcome.PASS, Severity.INFO)),
        ((Outcome.PASS, Severity.INFO), (Outcome.FAIL, Severity.REJECT)),
        ((Outcome.PASS, Severity.INFO), (Outcome.FAIL, Severity.WARN)),
        ((Outcome.NOT_APPLICABLE, Severity.INFO), (Outcome.INSUFFICIENT_EVIDENCE, Severity.REJECT)),
        ((Outcome.FAIL, Severity.WARN), (Outcome.FAIL, Severity.REJECT)),
    ],
)
async def test_the_trace_reproduces_the_engines_answer(monkeypatch, findings) -> None:
    """A correction is combined with the trace rows it leaves in place, so those
    rows must decide the label exactly as the engine did."""
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )
    rules = FakeRuleEngine(results=tuple(_vr(i, o, s) for i, (o, s) in enumerate(findings)))
    evaluator = Evaluator(
        vision=FakeVisionExtractor(observations=[]), rules=rules, settings=Settings()
    )
    env = await evaluator.evaluate(
        application=Application(
            application_id="A", evaluation_id="EV-T", beverage_class=BeverageClass.SPIRITS
        ),
        label=_stub_label(),
    )
    rows = [row.disposition for row in env.audit_trail.per_rule_trace]
    assert disposition_module._combine(rows) == env.disposition


# --------------------------------------------------------------------------
# The endpoint
# --------------------------------------------------------------------------


def _seeded(env: DispositionEnvelope):
    from app.api._sse_bus import SSEBus
    from app.batch.state import InFlightBatch
    from app.schemas.batch import BatchItem, ItemState

    app = create_app()
    item = BatchItem(
        label_id="lbl-c",
        application_ref="app-c",
        state=ItemState.QUEUED,
        result=None,
        enqueued_at=_NOW,
    )
    in_flight = InFlightBatch(batch_id="B-C", agent_id="a", items=(item,), lookahead_k=3)
    in_flight.results["lbl-c"] = env
    app.state.batches = {"B-C": in_flight}
    bus = SSEBus()
    app.state.buses = {"B-C": bus}
    return app, in_flight, bus


def _correct(client: TestClient, field_name: str | None, applied: str):
    return client.post(
        "/labels/EV-C/overrides",
        json={
            "field_name": field_name,
            "applied_disposition": applied,
            "reason_code": f"REVIEWER.CORRECTION.{applied.upper()}",
        },
    )


def test_a_field_correction_moves_the_stored_result_and_says_so() -> None:
    env = _envelope({"brand_name": "fail", "alcohol_content": "pass"}, disposition="fail")
    app, in_flight, bus = _seeded(env)
    broadcasts: list[dict] = []
    bus.broadcast = broadcasts.append  # type: ignore[method-assign]

    resp = _correct(TestClient(app), "brand_name", "pass")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["field_name"] == "brand_name"
    # Measured against the field's own card, not the label's result.
    assert body["original_disposition"] == "fail"
    assert body["label_disposition"] == "pass"
    assert in_flight.results["lbl-c"].disposition == "pass"
    [event] = broadcasts
    assert event["event"] == "override-applied"
    assert event["data"]["label_disposition"] == "pass"


def test_a_correction_to_a_field_the_check_has_no_result_for_is_refused() -> None:
    env = _envelope({"brand_name": "pass"}, disposition="pass")
    app, in_flight, _bus = _seeded(env)

    resp = _correct(TestClient(app), "country_of_origin", "fail")

    assert resp.status_code == 400
    assert in_flight.results["lbl-c"].audit_trail.overrides == ()


@pytest.mark.parametrize("applied", ["pass", "fail", "needs_review"])
def test_every_correction_code_the_page_sends_is_accepted(applied: str) -> None:
    env = _envelope({"brand_name": "needs_review"}, disposition="needs_review")
    app, _in_flight, _bus = _seeded(env)
    resp = _correct(TestClient(app), "brand_name", applied)
    assert resp.status_code == 200, resp.text
    assert resp.json()["label_disposition"] == applied
