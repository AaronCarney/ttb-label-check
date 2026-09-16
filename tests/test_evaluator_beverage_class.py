"""The application says which beverage the label is for, so the reader need not.

A reader reports what it can see on a label. Nothing on a bottle reliably says
"this is wine and not a spirit", and the application already answers it, so the
evaluator tags every reading with the class the application declared before the
rules run. Without that step a wine label reaches the spirits rule pack and none
of the wine rules ever fire.
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.schemas.application import Application
from app.schemas.expected import BeverageClass
from app.services.evaluator import Evaluator
from app.vision.quality import QualityReport
from tests._fakes.orchestrator import FakeOrchestrator
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
    """A rule engine that keeps the readings it was handed."""

    def __init__(self) -> None:
        super().__init__()
        self.seen = ()

    async def evaluate(self, observations, expected, context):
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


async def _classes_seen(application: Application) -> set[BeverageClass]:
    rules = _RecordingRuleEngine()
    evaluator = Evaluator(
        vision=_reader(), rules=rules, orchestrator=FakeOrchestrator(), settings=Settings()
    )
    await evaluator.evaluate(application=application, label=_stub_label())
    return {obs.beverage_class for obs in rules.seen}


@pytest.mark.asyncio
async def test_the_declared_class_replaces_the_readers_tag():
    seen = await _classes_seen(
        Application(
            application_id="A", evaluation_id="EV-001", beverage_class=BeverageClass.WINE
        )
    )
    assert seen == {BeverageClass.WINE}


@pytest.mark.asyncio
async def test_an_application_declaring_no_class_leaves_the_reading_alone():
    """Nothing in the product should invent a class the application never gave."""
    seen = await _classes_seen(Application(application_id="A", evaluation_id="EV-001"))
    assert seen == {BeverageClass.SPIRITS}


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
            vision=_reader(), rules=rules, orchestrator=FakeOrchestrator(),
            settings=Settings(), cache=cache,
        )
        await evaluator.evaluate(
            application=Application(
                application_id="A", evaluation_id="EV-001", beverage_class=beverage_class
            ),
            label=_stub_label(),
        )
        classes.append({obs.beverage_class for obs in rules.seen})
    assert classes == [{BeverageClass.WINE}, {BeverageClass.MALT}]
