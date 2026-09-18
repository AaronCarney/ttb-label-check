"""The `engine_failure/` prefix on an engine failure's audit-trail row.

That prefix is what tells an engine failure apart from a rule outcome in the
audit trail, and the reviewer's page depends on it: `engineFailureCode` in
`frontend/src/lib/incompleteCheck.ts` finds the row naming why a check did not
finish by matching it. Reading `per_rule_trace[0]` instead — which is what the
batch panel used to do — finds `ENGINE.RULE_PACK.SELECTED`, because
which rules answered is recorded before anything can go wrong and so leads
every trace.

This test fails if the prefix moves, so the two sides cannot drift apart
silently.
"""

import asyncio

import pytest

from app.config import Settings
from app.schemas.application import Application
from app.schemas.expected import BeverageClass
from app.services.evaluator import Evaluator
from app.vision.quality import QualityReport
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_label

_ENGINE_FAILURE_PREFIX = "engine_failure/"


@pytest.mark.asyncio
async def test_a_stopped_evaluation_marks_its_failure_row_and_nothing_else(monkeypatch):
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
    e._sla_seconds = 0.05
    envelope = await e.evaluate(
        application=Application(
            application_id="A",
            evaluation_id="EV-EF-1",
            beverage_class=BeverageClass.SPIRITS,
        ),
        label=_stub_label(),
    )

    by_rule = {entry.rule_id: entry.evidence_ref for entry in envelope.audit_trail.per_rule_trace}
    assert by_rule["ENGINE.SLA.TIMEOUT"].startswith(_ENGINE_FAILURE_PREFIX)
    # The rule-pack row leads every trace and is not a failure. If it ever
    # carried the prefix, the reviewer's page would report rule-pack selection
    # as the reason a check did not finish.
    assert not by_rule["ENGINE.RULE_PACK.SELECTED"].startswith(_ENGINE_FAILURE_PREFIX)
