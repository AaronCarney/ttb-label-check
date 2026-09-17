"""Evaluator-layer failure modes: every way an evaluation can go wrong, and the
disposition each one produces."""

import asyncio

import pytest

from app.config import Settings
from app.schemas.application import Application
from app.schemas.expected import BeverageClass
from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
from app.services.evaluator import Evaluator
from app.vision.quality import QualityReport
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_label


@pytest.fixture(autouse=True)
def _bypass_legibility(monkeypatch):
    """Bypass the image-quality gate, so the rule routing under test is not
    masked by the legibility short-circuit."""
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )


def _em():
    return EngineMeta(
        engine_version="t", rule_pack_version="t", rule_pack="t", started_at_ms=0, elapsed_ms=0
    )


def _stub_app():
    return Application(application_id="A-001", evaluation_id="EV-001")


@pytest.mark.asyncio
async def test_conflicting_rules():
    rules = FakeRuleEngine(
        results=(
            ValidationResult(
                rule_id="R-A",
                cfr_citation="27 CFR §1",
                beverage_class=BeverageClass.SPIRITS,
                outcome=Outcome.PASS,
                severity=Severity.INFO,
                aggregated_confidence=0.95,
                engine_meta=_em(),
            ),
            ValidationResult(
                rule_id="R-B",
                cfr_citation="27 CFR §2",
                beverage_class=BeverageClass.SPIRITS,
                outcome=Outcome.FAIL,
                severity=Severity.REJECT,
                reason_code="X.CONFLICT.DETECTED",
                aggregated_confidence=0.95,
                engine_meta=_em(),
            ),
        )
    )
    e = Evaluator(vision=FakeVisionExtractor(observations=[]), rules=rules, settings=Settings())
    envelope = await e.evaluate(application=_stub_app(), label=_stub_label())
    assert envelope.disposition == "fail"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason_code, outcome, case_label",
    [
        ("ENGINE.OBSERVATION.AMBIGUOUS", Outcome.INSUFFICIENT_EVIDENCE, "ambiguous-observation"),
        ("CLASS_TYPE.INPUT.UNKNOWN", Outcome.INSUFFICIENT_EVIDENCE, "unknown-class-type"),
        (
            "CLASS_TYPE.MATCH.APPLICATION_LABEL_DISAGREE",
            Outcome.INSUFFICIENT_EVIDENCE,
            "class-type-disagreement",
        ),
        ("ENGINE.MEASUREMENT.MISSING_DPI", Outcome.INSUFFICIENT_EVIDENCE, "missing-dpi"),
    ],
)
async def test_registry_reason_codes_route_to_needs_review(reason_code, outcome, case_label):
    """A rule that ends with too little evidence routes the whole evaluation to
    needs_review, whichever registry reason code it carries."""
    rules = FakeRuleEngine(
        results=(
            ValidationResult(
                rule_id=f"R-{case_label}",
                cfr_citation="27 CFR §x",
                beverage_class=BeverageClass.SPIRITS,
                outcome=outcome,
                severity=Severity.WARN,
                reason_code=reason_code,
                aggregated_confidence=0.4,
                engine_meta=_em(),
            ),
        )
    )
    e = Evaluator(vision=FakeVisionExtractor(observations=[]), rules=rules, settings=Settings())
    envelope = await e.evaluate(application=_stub_app(), label=_stub_label())
    assert envelope.disposition == "needs_review", f"{case_label} did not route to needs_review"
    rule_ids = {entry.rule_id for entry in envelope.audit_trail.per_rule_trace}
    assert reason_code in rule_ids, (
        f"{case_label}: YAML-registry reason_code {reason_code} not surfaced in "
        f"per_rule_trace ({rule_ids}) — production path emits this string verbatim"
    )


@pytest.mark.asyncio
async def test_validator_exception():
    class FailingRules(FakeRuleEngine):
        async def evaluate(self, *a, **kw):
            raise RuntimeError("validator boom")

    e = Evaluator(
        vision=FakeVisionExtractor(observations=[]),
        rules=FailingRules(results=()),
        settings=Settings(),
    )
    envelope = await e.evaluate(application=_stub_app(), label=_stub_label())
    assert envelope.disposition == "needs_review"


@pytest.mark.asyncio
async def test_per_rule_timeout_outcome_routes_to_needs_review():
    rules = FakeRuleEngine(
        results=(
            ValidationResult(
                rule_id="R-slow",
                cfr_citation="27 CFR §x",
                beverage_class=BeverageClass.SPIRITS,
                outcome=Outcome.TIMEOUT,
                severity=Severity.INFO,
                reason_code="ENGINE.SLA.RULE_TIMEOUT",
                aggregated_confidence=0.0,
                engine_meta=_em(),
            ),
            ValidationResult(
                rule_id="R-ok",
                cfr_citation="27 CFR §y",
                beverage_class=BeverageClass.SPIRITS,
                outcome=Outcome.PASS,
                severity=Severity.INFO,
                aggregated_confidence=0.95,
                engine_meta=_em(),
            ),
        )
    )
    e = Evaluator(vision=FakeVisionExtractor(observations=[]), rules=rules, settings=Settings())
    envelope = await e.evaluate(application=_stub_app(), label=_stub_label())
    assert envelope.disposition == "needs_review"


@pytest.mark.asyncio
async def test_whole_eval_timeout():
    class SlowRules(FakeRuleEngine):
        async def evaluate(self, *a, **kw):
            await asyncio.sleep(10)
            return ()

    e = Evaluator(
        vision=FakeVisionExtractor(observations=[]),
        rules=SlowRules(results=()),
        settings=Settings(),
    )
    e._sla_seconds = 0.1
    envelope = await e.evaluate(application=_stub_app(), label=_stub_label())
    assert envelope.disposition == "needs_review"
    rule_ids = {entry.rule_id for entry in envelope.audit_trail.per_rule_trace}
    assert "ENGINE.SLA.TIMEOUT" in rule_ids


@pytest.mark.asyncio
async def test_reference_data_unavailable():
    rules = FakeRuleEngine(
        results=(
            ValidationResult(
                rule_id="R-cpi",
                cfr_citation="27 CFR §x",
                beverage_class=BeverageClass.SPIRITS,
                outcome=Outcome.ERROR,
                severity=Severity.INFO,
                reason_code="ENGINE.REFERENCE_DATA.UNAVAILABLE",
                aggregated_confidence=0.0,
                engine_meta=_em(),
            ),
        )
    )
    e = Evaluator(vision=FakeVisionExtractor(observations=[]), rules=rules, settings=Settings())
    envelope = await e.evaluate(application=_stub_app(), label=_stub_label())
    assert envelope.disposition == "needs_review"


@pytest.mark.asyncio
async def test_short_circuit_preserves_prior_failures_in_audit():
    """When vision raises and the legibility gate also fires, both failures must
    surface in per_rule_trace. The _short_circuit path must not skip the loop
    that surfaces timeline.failures, or the earlier
    ENGINE.EXTRACTION.UNAVAILABLE entry is silently dropped from the audit."""

    class CrashingVision(FakeVisionExtractor):
        async def extract(self, label):
            raise RuntimeError("vision boom")

    e = Evaluator(
        vision=CrashingVision(observations=[]),
        rules=FakeRuleEngine(results=()),
        settings=Settings(),
    )
    # _stub_label ships 8-byte PNG-magic stub; assess_quality routes it to
    # needs_better_photo via the decode-error guard, triggering _short_circuit.
    envelope = await e.evaluate(application=_stub_app(), label=_stub_label())
    assert envelope.disposition == "needs_review"
    rule_ids = {entry.rule_id for entry in envelope.audit_trail.per_rule_trace}
    assert "ENGINE.EXTRACTION.UNAVAILABLE" in rule_ids, (
        f"audit dropped the prior vision failure on the legibility short-circuit "
        f"path; per_rule_trace = {rule_ids}"
    )
