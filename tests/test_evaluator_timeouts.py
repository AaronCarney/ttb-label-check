"""The whole-evaluation timeout, which emits ENGINE.SLA.TIMEOUT."""

import asyncio

import pytest

from app.config import Settings
from app.schemas.application import Application
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
