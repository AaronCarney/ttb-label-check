"""End-to-end via fakes — disposition + cache + envelope shape."""
import pytest

from app.config import Settings
from app.schemas.application import Application
from app.schemas.expected import BeverageClass
from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
from app.services.cache import SessionCache
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
async def test_happy_path_pass_disposition():
    rules = FakeRuleEngine(results=tuple(
        ValidationResult(rule_id=f"R-{i}", cfr_citation="27 CFR §x", beverage_class=BeverageClass.SPIRITS,
                         outcome=Outcome.PASS, severity=Severity.INFO, aggregated_confidence=1.0, engine_meta=_em())
        for i in range(3)
    ))
    e = Evaluator(vision=FakeVisionExtractor(observations=[]), rules=rules,
                  orchestrator=FakeOrchestrator(), settings=Settings())
    envelope = await e.evaluate(application=Application(application_id="A", evaluation_id="EV-001"), label=_stub_label())
    assert envelope.evaluation_id == "EV-001"
    assert envelope.disposition == "pass"
    assert envelope.audit_trail.input_hash != "0" * 64
    assert envelope.audit_trail.output_hash != "0" * 64


@pytest.mark.asyncio
async def test_fail_disposition():
    rules = FakeRuleEngine(results=(
        ValidationResult(rule_id="R-1", cfr_citation="27 CFR §x", beverage_class=BeverageClass.SPIRITS,
                         outcome=Outcome.FAIL, severity=Severity.REJECT, reason_code="X.FAIL.CASE",
                         aggregated_confidence=0.95, engine_meta=_em()),
    ))
    e = Evaluator(vision=FakeVisionExtractor(observations=[]), rules=rules,
                  orchestrator=FakeOrchestrator(), settings=Settings())
    envelope = await e.evaluate(application=Application(application_id="A", evaluation_id="EV-001"), label=_stub_label())
    assert envelope.disposition == "fail"


@pytest.mark.asyncio
async def test_cache_hit_replaces_evaluation_id():
    cache = SessionCache(maxsize=8)
    rules = FakeRuleEngine(results=())
    vision_calls = []

    class CountingVision(FakeVisionExtractor):
        async def extract(self, label):
            vision_calls.append(label.label_id)
            return await super().extract(label)

    e = Evaluator(vision=CountingVision(observations=[]), rules=rules,
                  orchestrator=FakeOrchestrator(), settings=Settings(), cache=cache)
    label = _stub_label()
    e1 = await e.evaluate(application=Application(application_id="A", evaluation_id="EV-1"), label=label)
    e2 = await e.evaluate(application=Application(application_id="A", evaluation_id="EV-2"), label=label)

    assert len(vision_calls) == 1, "cache miss: vision called twice"
    assert e2.evaluation_id == "EV-2"
    assert e2.audit_trail.evaluation_id == "EV-2", \
        "AC #12: cache hit must patch audit_trail.evaluation_id, not just envelope-level"
    assert e1.disposition == e2.disposition
