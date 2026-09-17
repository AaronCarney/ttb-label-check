"""The result cache must not replay measured timings, and must not survive a
change to the rules that produced the answer.

Two separate lies came out of the same hole: the Evaluator could reach the
rule engine's *results* but not its *identity*. So the cache key could not
carry which rules produced the answer, and the audit trail could not name
them either — `EvaluationTimeline.rule_set_version` defaults to "unknown" and
nothing in `app/` ever set it.
"""
from __future__ import annotations

import asyncio

import pytest

from app.config import Settings
from app.schemas.application import Application
from app.schemas.expected import BeverageClass
from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
from app.services.cache import SessionCache
from app.services.evaluator import Evaluator
from app.vision.quality import QualityReport
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_label as _label


@pytest.fixture(autouse=True)
def _bypass_legibility(monkeypatch):
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )


class _SlowVision(FakeVisionExtractor):
    """A reader that costs measurable wall-clock, so a replayed duration is
    distinguishable from a measured one."""

    def __init__(self, *, delay_s: float) -> None:
        super().__init__(observations=())
        self._delay_s = delay_s
        self.calls = 0

    async def extract(self, label):
        self.calls += 1
        await asyncio.sleep(self._delay_s)
        return []


def _rejecting_result() -> ValidationResult:
    return ValidationResult(
        rule_id="common.warning.present",
        cfr_citation="27 CFR §16.21",
        beverage_class=BeverageClass.SPIRITS,
        outcome=Outcome.FAIL,
        severity=Severity.REJECT,
        reason_code="WARNING.PRESENCE.MISSING",
        aggregated_confidence=1.0,
        engine_meta=EngineMeta(
            engine_version="test", rule_pack_version="0.1.0", rule_pack="common",
            started_at_ms=0, elapsed_ms=0,
        ),
    )


@pytest.mark.asyncio
async def test_a_cache_hit_reports_its_own_cost_not_the_first_call_s():
    vision = _SlowVision(delay_s=0.05)
    cache = SessionCache(maxsize=8)
    evaluator = Evaluator(
        vision=vision, rules=FakeRuleEngine(results=()), settings=Settings(), cache=cache,
    )
    label = _label()

    first = await evaluator.evaluate(
        application=Application(application_id="A", evaluation_id="EV-001"), label=label,
    )
    assert first.metrics.vision_duration_ms >= 40, "the first call really did read the label"
    assert first.metrics.cache_hit is False

    second = await evaluator.evaluate(
        application=Application(application_id="A", evaluation_id="EV-002"), label=label,
    )
    assert vision.calls == 1, "the second call was served from the cache"
    assert second.disposition == first.disposition, "it is the same answer"

    # ...and it says so, rather than reporting time it never spent.
    assert second.metrics.cache_hit is True
    assert second.metrics.vision_duration_ms == 0
    assert second.metrics.per_rule_durations_ms == ()
    assert second.metrics.total_duration_ms < 40


@pytest.mark.asyncio
async def test_a_cache_hit_dates_itself_to_the_request_it_answered():
    """The audit trail carries a new evaluation_id on a hit. Leaving the old
    timestamps beside it would date this evaluation to one that happened
    before it."""
    cache = SessionCache(maxsize=8)
    evaluator = Evaluator(
        vision=FakeVisionExtractor(), rules=FakeRuleEngine(results=()),
        settings=Settings(), cache=cache,
    )
    label = _label()

    first = await evaluator.evaluate(
        application=Application(application_id="A", evaluation_id="EV-001"), label=label,
    )
    await asyncio.sleep(0.01)
    second = await evaluator.evaluate(
        application=Application(application_id="A", evaluation_id="EV-002"), label=label,
    )

    assert second.audit_trail.evaluation_id == "EV-002"
    assert second.audit_trail.started_at > first.audit_trail.completed_at


@pytest.mark.asyncio
async def test_a_rule_pack_change_invalidates_the_cached_answer():
    """Same label, same application, edited rules — the label must be answered
    under the rules that now apply, not the ones that applied before."""
    cache = SessionCache(maxsize=8)
    label = _label()

    before = Evaluator(
        vision=FakeVisionExtractor(), rules=FakeRuleEngine(results=(), rule_set_version="0.1.0"),
        settings=Settings(), cache=cache,
    )
    first = await before.evaluate(
        application=Application(application_id="A", evaluation_id="EV-001"), label=label,
    )
    assert first.disposition == "needs_review"

    after = Evaluator(
        vision=FakeVisionExtractor(),
        rules=FakeRuleEngine(results=(_rejecting_result(),), rule_set_version="0.2.0"),
        settings=Settings(), cache=cache,
    )
    second = await after.evaluate(
        application=Application(application_id="A", evaluation_id="EV-002"), label=label,
    )
    assert second.disposition == "fail"


@pytest.mark.asyncio
async def test_the_audit_trail_names_the_rule_set_it_used():
    evaluator = Evaluator(
        vision=FakeVisionExtractor(), rules=FakeRuleEngine(results=(), rule_set_version="0.4.2"),
        settings=Settings(), cache=None,
    )
    envelope = await evaluator.evaluate(
        application=Application(application_id="A", evaluation_id="EV-001"), label=_label(),
    )
    assert envelope.audit_trail.rule_set_version == "0.4.2"


@pytest.mark.asyncio
async def test_the_real_rule_pack_is_named_in_the_audit_trail():
    """`unknown` is what every envelope this service has ever served carried."""
    from app.rules import build_rule_engine

    settings = Settings()
    evaluator = Evaluator(
        vision=FakeVisionExtractor(), rules=build_rule_engine(settings),
        settings=settings, cache=None,
    )
    envelope = await evaluator.evaluate(
        application=Application(application_id="A", evaluation_id="EV-001"), label=_label(),
    )
    assert envelope.audit_trail.rule_set_version != "unknown"
    assert envelope.audit_trail.rule_set_version.startswith("0.")
