"""The audit trail says what read the label, not just what judged it.

`AuditRecord.model_version` is the half of the compliance record that names the
reader. `rule_set_version` was fixed first and names the rules; until this,
`EvaluationTimeline.model_version` was assigned nowhere in `app/`, so the field
was `None` on every envelope the service has ever served.

It matters for the case the audit trail exists for. A producer contesting a
rejection is contesting a reading — the verdict follows from the text the
reader returned — and a record that cannot say which reader produced that text
cannot answer them. It also cannot tell two verdicts apart when the reader
changes underneath: the same label, read by a different engine version, can
give a different answer, and nothing in the record would show why.
"""

from __future__ import annotations

from importlib import metadata

import pytest

from app.config import Settings
from app.logging.ring_buffer import new_call_ring_buffer
from app.schemas.application import Application
from app.services.evaluator import Evaluator
from app.vision.base import VisionExtractor
from app.vision.cloud import CloudVisionExtractor
from app.vision.local import LocalVisionExtractor
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


def test_the_reader_seam_requires_a_version() -> None:
    """`reader_version` is part of the protocol, not an extra on one reader.

    A seam where only one side can name itself is not a seam the audit trail
    can rely on: swapping the reader would silently stop the record naming one.
    """
    assert hasattr(VisionExtractor, "reader_version")
    assert isinstance(FakeVisionExtractor(), VisionExtractor)


def test_the_local_reader_names_its_engine_and_the_installed_version() -> None:
    """Not a constant: the version comes from the package that is installed,
    so an upgrade changes the recorded value without anyone editing it."""
    reader = LocalVisionExtractor(settings=Settings(), ring_buffer=new_call_ring_buffer())
    assert reader.reader_version == f"local:rapidocr@{metadata.version('rapidocr')}"


def test_the_cloud_reader_names_the_pinned_model_snapshot() -> None:
    settings = Settings(OPENAI_API_KEY="k", LLM_MODEL_SNAPSHOT="gpt-4o-2024-08-06")
    reader = CloudVisionExtractor(
        settings=settings, ring_buffer=new_call_ring_buffer(), api_key="k"
    )
    assert reader.reader_version == "cloud:gpt-4o-2024-08-06"


@pytest.mark.asyncio
async def test_an_evaluation_records_which_reader_read_the_label() -> None:
    """The regression this file exists for: the field was `None` on every
    envelope, so `assert is not None` is the assertion that failed before."""
    reader = FakeVisionExtractor(observations=[])
    evaluator = Evaluator(
        vision=reader,
        rules=FakeRuleEngine(results=()),  # type: ignore[arg-type]
        settings=Settings(),
    )
    envelope = await evaluator.evaluate(
        application=Application(application_id="A", evaluation_id="EV-001"), label=_label()
    )
    assert envelope.audit_trail.model_version is not None
    assert envelope.audit_trail.model_version == reader.reader_version
