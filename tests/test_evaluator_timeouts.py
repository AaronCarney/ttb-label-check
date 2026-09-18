"""The whole-evaluation timeout, which emits ENGINE.SLA.TIMEOUT."""

import asyncio
import time

import pytest

from app.config import Settings
from app.schemas.application import Application
from app.schemas.expected import BeverageClass
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.services.evaluator import Evaluator
from app.vision.quality import QualityReport
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_label


@pytest.mark.asyncio
async def test_whole_eval_timeout_routes_to_needs_review(monkeypatch):
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )

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
    envelope = await e.evaluate(
        application=Application(application_id="A", evaluation_id="EV-001"),
        label=_stub_label(),
    )
    assert envelope.disposition == "needs_review"
    rule_ids = {entry.rule_id for entry in envelope.audit_trail.per_rule_trace}
    assert "ENGINE.SLA.TIMEOUT" in rule_ids


# --- The timeout returns what was completed, rather than discarding it ---
#
# `docs/research/2026-09-15-rule-engine-architecture.md:772` row 10 specifies
# the whole-evaluation timeout as "needs_review whole-evaluation; partial
# results returned", carrying "partial results, last completed rule". Previously
# the code returned an envelope with no fields and
# `total_duration_ms: 0`, so a read that had finished was thrown away along
# with the rules that had not started. Measured live, the same
# label submitted four times returned all seven fields once and none three
# times, on a difference of about fifty milliseconds, with
# `vision_duration_ms` reading 4911 and 4900 on two of the blank ones — the
# read had completed and was discarded.


def _reading(field_id: str, value: str) -> FieldObservation:
    return FieldObservation(
        field_id=field_id,
        beverage_class=BeverageClass.SPIRITS,
        observed_value=value,
        evidence=(
            Evidence(
                field_id=field_id,
                source=EvidenceSource.OCR,
                bbox=(0, 0, 10, 10),
                match_kind=MatchKind.EXACT,
                confidence=0.9,
            ),
        ),
    )


def _slow_rules_evaluator(observations) -> Evaluator:
    class SlowRules(FakeRuleEngine):
        async def evaluate(self, *a, **kw):
            await asyncio.sleep(10)
            return ()

    e = Evaluator(
        vision=FakeVisionExtractor(observations=observations),
        rules=SlowRules(results=()),
        settings=Settings(),
    )
    e._sla_seconds = 0.1
    return e


@pytest.mark.asyncio
async def test_timeout_returns_the_readings_the_reader_completed(monkeypatch):
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )
    e = _slow_rules_evaluator(
        [_reading("brand_name", "Old Overholt"), _reading("abv", "50% alc/vol")]
    )
    envelope = await e.evaluate(
        application=Application(
            application_id="A",
            evaluation_id="EV-002",
            beverage_class=BeverageClass.SPIRITS,
        ),
        label=_stub_label(),
    )

    assert envelope.disposition == "needs_review"
    assert "ENGINE.SLA.TIMEOUT" in {entry.rule_id for entry in envelope.audit_trail.per_rule_trace}
    read = {f.field_name: f.extracted_value for f in envelope.fields}
    assert read == {"brand_name": "Old Overholt", "alcohol_content": "50% alc/vol"}


@pytest.mark.asyncio
async def test_timeout_reports_the_time_it_actually_spent(monkeypatch):
    """`total_duration_ms: 0` said the check cost nothing, which is the one
    thing it certainly did not."""
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )
    e = _slow_rules_evaluator([_reading("brand_name", "Old Overholt")])
    envelope = await e.evaluate(
        application=Application(
            application_id="A",
            evaluation_id="EV-003",
            beverage_class=BeverageClass.SPIRITS,
        ),
        label=_stub_label(),
    )
    assert envelope.metrics.total_duration_ms > 0


# --- The cutoff is a runaway guard, not the requirement's own number ---
#
# `_DEFAULT_SLA_SECONDS = 5.0` was the same 5.0 seconds R15/NFR-1 measures, so
# every check that ran even slightly over the requirement was truncated rather
# than merely slow. That guarantees the worst reading of a marginal check: a
# partial answer where a complete one was a fifth of a second away. A cutoff on
# the requirement's own number cannot help the requirement either — a truncated
# check does not "show its results within 5 seconds" any more than a slow
# complete one does.
#
# The slowest whole check measured on the live service was 5.04 s
# (`docs/decisions.md#0035`, measured against deployed commit `8cb5e70`). A guard
# has to sit clear of the slowest legitimate check, not on it.
_SLOWEST_LIVE_CHECK_SECONDS = 5.04


def test_the_guard_sits_clear_of_the_requirements_budget():
    """The guard catches an evaluation that has gone wrong. It must not catch
    one that is merely slower than the requirement wanted."""
    from tests.test_deploy_healthz import _LATENCY_BUDGET_SECONDS

    guard = Settings().evaluation_guard_seconds
    assert guard > _LATENCY_BUDGET_SECONDS + _SLOWEST_LIVE_CHECK_SECONDS


def test_the_guard_is_configurable_without_a_code_change(monkeypatch):
    monkeypatch.setenv("EVALUATION_GUARD_SECONDS", "12.5")
    assert Settings().evaluation_guard_seconds == 12.5


@pytest.mark.asyncio
async def test_the_evaluator_takes_its_guard_from_settings(monkeypatch):
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )

    class SlowRules(FakeRuleEngine):
        async def evaluate(self, *a, **kw):
            await asyncio.sleep(10)
            return ()

    e = Evaluator(
        vision=FakeVisionExtractor(observations=[]),
        rules=SlowRules(results=()),
        settings=Settings(evaluation_guard_seconds=0.05),
    )
    started = time.monotonic()
    envelope = await e.evaluate(
        application=Application(application_id="A", evaluation_id="EV-004"),
        label=_stub_label(),
    )
    elapsed = time.monotonic() - started
    assert "ENGINE.SLA.TIMEOUT" in {entry.rule_id for entry in envelope.audit_trail.per_rule_trace}
    # The setting, not the class default, is what stopped it: 0.05 s is the
    # configured guard and 5.0 s was the old hard-coded one.
    assert elapsed < 1.0


@pytest.mark.slow
@pytest.mark.asyncio
async def test_a_check_that_overruns_the_requirement_still_finishes(monkeypatch):
    """The behaviour the guard's number is chosen for: a check that takes
    longer than the five seconds R15 asks for comes back complete, slowly,
    rather than truncated. Runs at the default guard on purpose — the number
    under test is the shipped one."""
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )
    from tests.test_deploy_healthz import _LATENCY_BUDGET_SECONDS

    class OverrunningRules(FakeRuleEngine):
        async def evaluate(self, *a, **kw):
            await asyncio.sleep(_LATENCY_BUDGET_SECONDS + 0.3)
            return ()

    e = Evaluator(
        vision=FakeVisionExtractor(observations=[_reading("brand_name", "Old Overholt")]),
        rules=OverrunningRules(results=()),
        settings=Settings(),
    )
    envelope = await e.evaluate(
        application=Application(
            application_id="A",
            evaluation_id="EV-005",
            beverage_class=BeverageClass.SPIRITS,
        ),
        label=_stub_label(),
    )
    trace = {entry.rule_id for entry in envelope.audit_trail.per_rule_trace}
    assert "ENGINE.SLA.TIMEOUT" not in trace
    assert envelope.metrics.total_duration_ms > _LATENCY_BUDGET_SECONDS * 1000
