"""A photo the reader finds no text on stops the label, under a code of its own.

The detector finding nothing, at every rotation it tries, is the one sign that
a photograph cannot be checked that does not guess at the cause. The reader
says so; the evaluator checks nothing on that label and carries the reader's
code and the face to the result, so the page can say which photo to retake
and how.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.schemas.application import Application
from app.schemas.label import Face
from app.services.evaluator import Evaluator
from app.vision.faces import QUALITY_FIELD_ID, is_unreadable
from app.vision.local import _no_text_reading
from app.vision.quality import QualityReport
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_label

NO_TEXT = "LEGIBILITY.PHOTO.NO_TEXT"


def _face(tag: str = "back") -> Face:
    return Face(image_bytes=b"\x89PNG\r\n\x1a\n", content_type="image/png", face_tag=tag)


def test_the_reader_names_no_text_and_the_face_not_low_resolution() -> None:
    reading = _no_text_reading(_face("back"), {"boxes_found": 0})
    assert is_unreadable(reading)
    (obs,) = reading
    assert obs.field_id == QUALITY_FIELD_ID
    assert obs.upstream_meta["reason_code"] == NO_TEXT
    assert obs.upstream_meta["face_tag"] == "back"
    assert obs.evidence[0].extracted_text == NO_TEXT


def _photo_passes_the_pixel_gates(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda face: QualityReport(disposition="ok", reason_code=None, dpi=300),
    )


@pytest.mark.asyncio
async def test_the_evaluator_checks_nothing_and_carries_the_reader_s_code(monkeypatch) -> None:
    _photo_passes_the_pixel_gates(monkeypatch)
    evaluator = Evaluator(
        vision=FakeVisionExtractor(observations=_no_text_reading(_face("back"), {})),
        rules=FakeRuleEngine(results=()),
        settings=Settings(),
    )
    envelope = await evaluator.evaluate(
        application=Application(application_id="A-001", evaluation_id="EV-001"),
        label=_stub_label(face_tag="back"),
    )
    assert envelope.disposition == "needs_review"
    assert envelope.fields == ()
    entries = [e for e in envelope.audit_trail.per_rule_trace if e.rule_id == NO_TEXT]
    assert len(entries) == 1
    assert entries[0].evidence_ref == f"engine_failure/{NO_TEXT}/back"


@pytest.mark.asyncio
async def test_a_pixel_gate_failure_also_names_its_face(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.evaluator.assess_quality",
        lambda face: QualityReport(
            disposition="needs_better_photo",
            reason_code="WARNING.LEGIBILITY.MOTION_BLUR",
            dpi=300,
        ),
    )
    evaluator = Evaluator(
        vision=FakeVisionExtractor(observations=[]),
        rules=FakeRuleEngine(results=()),
        settings=Settings(),
    )
    envelope = await evaluator.evaluate(
        application=Application(application_id="A-001", evaluation_id="EV-001"),
        label=_stub_label(face_tag="neck"),
    )
    refs = {
        e.evidence_ref
        for e in envelope.audit_trail.per_rule_trace
        if e.rule_id == "WARNING.LEGIBILITY.MOTION_BLUR"
    }
    assert "engine_failure/WARNING.LEGIBILITY.MOTION_BLUR/neck" in refs
