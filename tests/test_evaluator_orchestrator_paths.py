"""Orchestrator trigger fires/doesn't fire correctly + patcher integrates."""
import pytest

from app.config import Settings
from app.schemas.application import Application
from app.schemas.expected import BeverageClass
from app.schemas.refined import Refined, TaskSlice
from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
from app.services.evaluator import Evaluator
from app.vision.quality import QualityReport
from tests._fakes.orchestrator import FakeOrchestrator
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_label


def _em():
    return EngineMeta(engine_version="t", rule_pack_version="t", rule_pack="t", started_at_ms=0, elapsed_ms=0)


@pytest.fixture(autouse=True)
def _bypass_legibility(monkeypatch):
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )


@pytest.mark.asyncio
async def test_orchestrator_not_invoked_when_no_trigger():
    rules = FakeRuleEngine(results=tuple(
        ValidationResult(rule_id=f"R-{i}", cfr_citation="27 CFR §x", beverage_class=BeverageClass.SPIRITS,
                         outcome=Outcome.PASS, severity=Severity.INFO, aggregated_confidence=0.95, engine_meta=_em())
        for i in range(3)
    ))
    orch = FakeOrchestrator()
    e = Evaluator(vision=FakeVisionExtractor(observations=[]), rules=rules, orchestrator=orch, settings=Settings())
    await e.evaluate(application=Application(application_id="A", evaluation_id="EV-001"), label=_stub_label())
    assert orch.call_count == 0


@pytest.mark.asyncio
async def test_orchestrator_invoked_on_brand_needs_review():
    rules = FakeRuleEngine(results=(
        ValidationResult(rule_id="X.brand.present", cfr_citation="27 CFR §5.42",
                         beverage_class=BeverageClass.SPIRITS, outcome=Outcome.INSUFFICIENT_EVIDENCE,
                         severity=Severity.WARN, reason_code="BRAND.NAME.NEEDS_REVIEW",
                         aggregated_confidence=0.6, engine_meta=_em()),
    ))
    canned = Refined(evaluation_id="EV-001", tasks=(
        TaskSlice(task="brand_disambig", rule_id="X.brand.present",
                  payload={"decision": "match", "justification": "phonetic"}),
    ))
    orch = FakeOrchestrator(refined_outputs=[canned])
    e = Evaluator(vision=FakeVisionExtractor(observations=[]), rules=rules, orchestrator=orch,
                  settings=Settings(orchestrator_enabled=True))
    await e.evaluate(application=Application(application_id="A", evaluation_id="EV-001"), label=_stub_label())
    assert orch.call_count == 1


@pytest.mark.asyncio
async def test_orchestrator_skipped_when_disabled_even_on_trigger():
    """Master-switch contract: settings.orchestrator_enabled=False bars
    invocation even when the brand-needs-review trigger code is present.
    This is the default. The schemas already keep the model out of the verdict;
    the switch is defence in depth, and it is what lets the product check labels
    with no outbound call at all."""
    rules = FakeRuleEngine(results=(
        ValidationResult(rule_id="X.brand.present", cfr_citation="27 CFR §5.42",
                         beverage_class=BeverageClass.SPIRITS, outcome=Outcome.INSUFFICIENT_EVIDENCE,
                         severity=Severity.WARN, reason_code="BRAND.NAME.NEEDS_REVIEW",
                         aggregated_confidence=0.6, engine_meta=_em()),
    ))
    orch = FakeOrchestrator()
    e = Evaluator(vision=FakeVisionExtractor(observations=[]), rules=rules, orchestrator=orch,
                  settings=Settings(orchestrator_enabled=False))
    await e.evaluate(application=Application(application_id="A", evaluation_id="EV-001"), label=_stub_label())
    assert orch.call_count == 0
