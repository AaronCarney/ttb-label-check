"""Fakes must conform to the real seams' interfaces."""
import inspect

import pytest

from app.orchestrator.base import Orchestrator
from app.rules.engine import RuleEngine
from app.schemas.application import Application
from app.schemas.refined import Refined
from tests._fakes.orchestrator import FakeOrchestrator
from tests._fakes.rules import FakeRuleEngine


def test_fake_orchestrator_subclasses_orchestrator():
    assert issubclass(FakeOrchestrator, Orchestrator)


def test_fake_orchestrator_refine_is_coroutine():
    assert inspect.iscoroutinefunction(FakeOrchestrator.refine)


@pytest.mark.asyncio
async def test_fake_orchestrator_returns_canned_refined():
    canned = Refined(evaluation_id="EV-001")
    fake = FakeOrchestrator(refined_outputs=[canned])
    out = await fake.refine(application=Application(application_id="A", evaluation_id="EV-001"), observations=[], validation_results=[])
    assert out == canned
    assert fake.call_count == 1


@pytest.mark.asyncio
async def test_fake_orchestrator_can_raise_on_nth_call():
    fake = FakeOrchestrator(refined_outputs=[Refined(evaluation_id="EV-001")], raise_on_call=1)
    with pytest.raises(RuntimeError):
        await fake.refine(application=Application(application_id="A", evaluation_id="EV-001"), observations=[], validation_results=[])


def test_fake_rule_engine_subclasses_rule_engine():
    assert issubclass(FakeRuleEngine, RuleEngine)


@pytest.mark.asyncio
async def test_fake_rule_engine_returns_canned_results():
    from app.schemas.expected import BeverageClass
    from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult

    em = EngineMeta(engine_version="t", rule_pack_version="t", rule_pack="t", started_at_ms=0, elapsed_ms=0)
    canned = (
        ValidationResult(
            rule_id="R-001", cfr_citation="27 CFR §x", beverage_class=BeverageClass.SPIRITS,
            outcome=Outcome.PASS, severity=Severity.INFO, aggregated_confidence=1.0, engine_meta=em,
        ),
    )
    fake = FakeRuleEngine(results=canned)
    out = await fake.evaluate(observations=[], expected=[], context=None)  # type: ignore[arg-type]
    assert out == canned


def test_fake_rule_engine_build_validator_context_returns_stub():
    """``RuleEngine`` declares ``build_validator_context`` abstract, so the fake
    must implement it: otherwise `FakeRuleEngine(...)` cannot be instantiated,
    and the Evaluator cannot call `self._rules.build_validator_context(...)`
    through the abstraction."""
    from app.rules._validators import ValidatorContext

    fake = FakeRuleEngine(results=())
    ctx = fake.build_validator_context(started_at_ms=42)
    assert isinstance(ctx, ValidatorContext)
    assert ctx.assets == {}
    assert ctx.decision_tables == {}
    assert ctx.started_at_ms == 42
    assert ctx.engine_version == "fake"
