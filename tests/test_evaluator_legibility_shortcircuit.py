"""Quality.assess returns needs_better_photo → short-circuit to needs_review."""
import pytest

from app.config import Settings
from app.schemas.application import Application
from app.services.evaluator import Evaluator
from app.vision.quality import QualityReport
from tests._fakes.orchestrator import FakeOrchestrator
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_label


@pytest.mark.asyncio
async def test_legibility_short_circuit(monkeypatch):
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda lbl: QualityReport(
            disposition="needs_better_photo",
            reason_code="WARNING.LEGIBILITY.LOW_DPI",
            dpi=72,
        ),
    )
    evaluator = Evaluator(vision=FakeVisionExtractor(observations=[]),
                          rules=FakeRuleEngine(results=()),
                          orchestrator=FakeOrchestrator(), settings=Settings())
    envelope = await evaluator.evaluate(
        application=Application(application_id="A-001", evaluation_id="EV-001"),
        label=_stub_label(),
    )
    assert envelope.disposition == "needs_review"
    rule_ids = {entry.rule_id for entry in envelope.audit_trail.per_rule_trace}
    assert "WARNING.LEGIBILITY.LOW_DPI" in rule_ids


@pytest.mark.asyncio
async def test_stub_label_bytes_route_to_needs_review_without_raising():
    """An eight-byte PNG header must not crash assess_quality: a truncated or
    unreadable image comes back as needs_review, not as an exception."""
    evaluator = Evaluator(vision=FakeVisionExtractor(observations=[]),
                          rules=FakeRuleEngine(results=()),
                          orchestrator=FakeOrchestrator(), settings=Settings())
    envelope = await evaluator.evaluate(
        application=Application(application_id="A-001", evaluation_id="EV-001"),
        label=_stub_label(),  # default eight-byte PNG-magic stub bytes
    )
    assert envelope.disposition == "needs_review"
    rule_ids = {entry.rule_id for entry in envelope.audit_trail.per_rule_trace}
    assert "WARNING.LEGIBILITY.LOW_RESOLUTION" in rule_ids
