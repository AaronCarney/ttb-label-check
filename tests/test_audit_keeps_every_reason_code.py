"""Every rule that did not pass keeps its own reason code in the audit trail.

The audit trail gives each such rule a second entry, named by its reason code,
whose `evidence_ref` (`reason_code/<rule id>`) says which rule it belongs to.
The timeline once stored its rows under the entry's name, so where two rules
reported the same code — the three warning rules all report
`WARNING.HEADING.NOT_READ` when the statement's words were read and its heading
was not — each row overwrote the one before, and the record kept the code for
only the last rule. The others read as sent to a reviewer for no stated reason.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.schemas.application import Application
from app.schemas.expected import BeverageClass, ExpectedValue
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
from app.services.engine_meta import EvaluationTimeline
from app.services.evaluator import Evaluator
from app.vision.quality import QualityReport
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_label as _label

_CODE = "WARNING.HEADING.NOT_READ"
_RULES = ("common.warning.heading_caps_bold", "common.warning.present", "common.warning.verbatim")


@pytest.fixture(autouse=True)
def _bypass_legibility(monkeypatch):
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )


def _result(rule_id: str) -> ValidationResult:
    evidence = Evidence(
        field_id="gov_warning",
        source=EvidenceSource.LAYOUT,
        match_kind=MatchKind.NONE,
        confidence=0.9,
    )
    return ValidationResult(
        rule_id=rule_id,
        cfr_citation="27 CFR §16.21",
        beverage_class=BeverageClass.SPIRITS,
        outcome=Outcome.INSUFFICIENT_EVIDENCE,
        severity=Severity.WARN,
        reason_code=_CODE,
        aggregated_confidence=0.9,
        evidence=(evidence,),
        expected=ExpectedValue(field_id="gov_warning"),
        observed=FieldObservation(
            field_id="gov_warning",
            beverage_class=BeverageClass.SPIRITS,
            observed_value={"text": "", "wording_without_heading": True},
            evidence=(evidence,),
            upstream_meta={},
        ),
        engine_meta=EngineMeta(
            engine_version="t",
            rule_pack_version="t",
            rule_pack="t",
            started_at_ms=0,
            elapsed_ms=0,
        ),
    )


@pytest.mark.asyncio
async def test_rules_sharing_a_reason_code_each_keep_it() -> None:
    e = Evaluator(
        vision=FakeVisionExtractor(observations=[]),
        rules=FakeRuleEngine(results=tuple(_result(r) for r in _RULES)),
        settings=Settings(),
    )
    envelope = await e.evaluate(
        application=Application(application_id="A", evaluation_id="EV-001"), label=_label()
    )
    trace = envelope.audit_trail.per_rule_trace
    code_rows = {
        e.evidence_ref.removeprefix("reason_code/"): e.rule_id
        for e in trace
        if e.evidence_ref.startswith("reason_code/")
    }
    assert code_rows == dict.fromkeys(_RULES, _CODE)


def test_recording_the_same_row_twice_still_rewrites_it() -> None:
    """The timeout path records finished rules a second time; that must not
    duplicate their rows."""
    t = EvaluationTimeline(evaluation_id="EV-001")
    for _ in range(2):
        t.record_rule_done(
            rule_id=_CODE, duration_ms=0, disposition="needs_review", evidence_ref="reason_code/a"
        )
    assert len(t.per_rule_durations) == 1
