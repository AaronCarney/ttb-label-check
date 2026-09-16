"""The application says which beverage the label is for, so the reader need not.

A reader reports what it can see on a label. Nothing on a bottle reliably says
"this is wine and not a spirit", and the application already answers it, so the
evaluator tags every reading with the class the application declared before the
rules run. Without that step a wine label reaches the spirits rule pack and none
of the wine rules ever fire.

Where the application names no class there is nothing to tag with, and the
reader's own tag is not a substitute: both readers call everything they see
spirits. So no rule runs, and the audit trail says so. `docs/decisions.md#0010`
carries the argument; `tests/rules/test_label_matches_application.py`'s
`test_no_application_means_no_comparison_applies` states the matching contract
on the rules side.
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.schemas.application import Application
from app.schemas.expected import BeverageClass
from app.services.evaluator import Evaluator
from app.vision.quality import QualityReport
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_label
from tests.rules.fixtures import make_obs


@pytest.fixture(autouse=True)
def _bypass_legibility(monkeypatch):
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )


class _RecordingRuleEngine(FakeRuleEngine):
    """A rule engine that keeps the readings it was handed, and counts calls.

    The count matters: "the rules saw no readings" and "the rules were never
    reached" look identical from `seen` alone, and only the first is what the
    evaluator should do with an unclassified label.
    """

    def __init__(self) -> None:
        super().__init__()
        self.seen = ()
        self.calls = 0

    async def evaluate(self, observations, expected, context):
        self.calls += 1
        self.seen = tuple(observations)
        return ()


def _reader():
    """A reader whose readings are tagged spirits, whatever the label is."""
    return FakeVisionExtractor(
        observations=[
            make_obs(
                field_id="brand_name",
                value={"brand_name": "Stone's Throw", "confidence": 0.95},
                beverage_class=BeverageClass.SPIRITS,
            ),
            make_obs(
                field_id="class_type",
                value={"class_type": "TABLE WHITE WINE", "confidence": 0.95},
                beverage_class=BeverageClass.SPIRITS,
            ),
        ]
    )


async def _evaluate(application: Application):
    """One evaluation; the readings the rules were handed, and the envelope."""
    rules = _RecordingRuleEngine()
    evaluator = Evaluator(
        vision=_reader(), rules=rules, settings=Settings()
    )
    envelope = await evaluator.evaluate(application=application, label=_stub_label())
    return rules, envelope


async def _classes_seen(application: Application) -> set[BeverageClass]:
    rules, _ = await _evaluate(application)
    return {obs.beverage_class for obs in rules.seen}


def _pack_row(envelope):
    """The audit-trail row naming the rules this evaluation ran."""
    rows = [
        entry for entry in envelope.audit_trail.per_rule_trace
        if entry.rule_id.startswith("ENGINE.RULE_PACK.")
    ]
    assert len(rows) == 1, [e.rule_id for e in envelope.audit_trail.per_rule_trace]
    return rows[0]


@pytest.mark.asyncio
async def test_the_declared_class_replaces_the_readers_tag():
    seen = await _classes_seen(
        Application(
            application_id="A", evaluation_id="EV-001", beverage_class=BeverageClass.WINE
        )
    )
    assert seen == {BeverageClass.WINE}


@pytest.mark.asyncio
async def test_an_application_declaring_no_class_gets_no_rules_at_all():
    """Nothing in the product may invent a class the application never gave.

    The reader's tag is not a fallback — it says spirits for every label it
    has ever seen — so an image filed without an application is checked
    against nothing rather than against the spirits pack.
    """
    rules, _ = await _evaluate(Application(application_id="A", evaluation_id="EV-001"))
    assert rules.calls == 1
    assert rules.seen == ()


@pytest.mark.asyncio
async def test_the_envelope_names_the_rules_that_ran():
    """A reviewer cannot tell from a verdict which rules produced it, and
    cannot reconstruct it later, so the audit trail states it."""
    _, envelope = await _evaluate(
        Application(
            application_id="A", evaluation_id="EV-001", beverage_class=BeverageClass.WINE
        )
    )
    row = _pack_row(envelope)
    assert row.rule_id == "ENGINE.RULE_PACK.SELECTED"
    assert row.evidence_ref == "rule_pack/wine"


@pytest.mark.asyncio
async def test_the_envelope_says_when_no_rules_could_be_chosen():
    """The one thing an image-only upload must not look like is a label that
    passed every check."""
    _, envelope = await _evaluate(Application(application_id="A", evaluation_id="EV-001"))
    row = _pack_row(envelope)
    assert row.rule_id == "ENGINE.RULE_PACK.NOT_SELECTED"
    assert row.evidence_ref == "rule_pack/none"
    assert row.disposition == "needs_review"


@pytest.mark.asyncio
async def test_two_classes_do_not_share_a_cached_result():
    """The same image filed as wine and as a malt beverage is two different
    checks, so the evaluation cache must not answer one with the other."""
    from app.services.cache import SessionCache

    cache = SessionCache(maxsize=8)
    classes = []
    for beverage_class in (BeverageClass.WINE, BeverageClass.MALT):
        rules = _RecordingRuleEngine()
        evaluator = Evaluator(
            vision=_reader(), rules=rules, settings=Settings(), cache=cache,
        )
        await evaluator.evaluate(
            application=Application(
                application_id="A", evaluation_id="EV-001", beverage_class=beverage_class
            ),
            label=_stub_label(),
        )
        classes.append({obs.beverage_class for obs in rules.seen})
    assert classes == [{BeverageClass.WINE}, {BeverageClass.MALT}]
