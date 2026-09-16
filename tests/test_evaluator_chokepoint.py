"""P4 chokepoint: vision/rules exceptions route to needs_review."""
import logging

import pytest

from app.config import Settings
from app.schemas.application import Application
from app.services.evaluator import Evaluator
from app.vision.quality import QualityReport
from tests._fakes.orchestrator import FakeOrchestrator
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_label as _label


@pytest.fixture(autouse=True)
def _bypass_legibility(monkeypatch):
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )


@pytest.mark.asyncio
async def test_vision_exception_routes_to_needs_review(caplog):
    caplog.set_level(logging.INFO, logger="app.services.evaluator")

    class FailingVision:
        async def extract(self, label):
            raise RuntimeError("vision boom")
        async def ensure_loaded(self):
            return None

    e = Evaluator(vision=FailingVision(), rules=FakeRuleEngine(results=()),  # type: ignore[arg-type]
                  orchestrator=FakeOrchestrator(), settings=Settings())
    envelope = await e.evaluate(application=Application(application_id="A", evaluation_id="EV-001"), label=_label())
    assert envelope.disposition == "needs_review"
    rule_ids = {entry.rule_id for entry in envelope.audit_trail.per_rule_trace}
    assert any("VISION" in c or "EXTRACTION" in c for c in rule_ids)
    assert any(
        getattr(r, "reason_code", None) == "ENGINE.EXTRACTION.UNAVAILABLE"
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_rule_engine_exception_routes_to_needs_review(caplog):
    caplog.set_level(logging.INFO, logger="app.services.evaluator")

    class FailingRules(FakeRuleEngine):
        async def evaluate(self, *a, **kw):
            raise RuntimeError("rules boom")

    e = Evaluator(vision=FakeVisionExtractor(observations=[]),
                  rules=FailingRules(results=()),
                  orchestrator=FakeOrchestrator(), settings=Settings())
    envelope = await e.evaluate(application=Application(application_id="A", evaluation_id="EV-001"), label=_label())
    assert envelope.disposition == "needs_review"
    assert any(
        getattr(r, "reason_code", None) == "ENGINE.RULES.UNAVAILABLE"
        for r in caplog.records
    )
