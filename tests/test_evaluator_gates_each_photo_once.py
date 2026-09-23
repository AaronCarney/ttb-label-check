"""Each photograph passes the image-quality gates once per check, not twice.

Both readers run `app.vision.quality.assess` on every face before reading it
and answer the first face it refuses with that refusal, so a reading that comes
back has already passed the gates on every face. The evaluator runs them itself
only where the reader answered nothing at all — a reader that failed — so a
blurred photograph is still named as one there.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.schemas.application import Application
from app.schemas.expected import BeverageClass
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.services.evaluator import Evaluator
from app.vision.faces import QUALITY_FIELD_ID
from app.vision.quality import QualityReport
from tests._fakes.rules import FakeRuleEngine
from tests._fakes.vision import FakeVisionExtractor
from tests.conftest import _stub_label


def _brand_read() -> FieldObservation:
    return FieldObservation(
        field_id="brand_name",
        beverage_class=BeverageClass.SPIRITS,
        observed_value={"text": "OLD TOM", "confidence": 0.9},
        evidence=(
            Evidence(
                field_id="brand_name",
                source=EvidenceSource.OCR,
                panel="front",
                bbox=(0, 0, 10, 10),
                extracted_text="OLD TOM",
                match_kind=MatchKind.NONE,
                confidence=0.9,
            ),
        ),
        upstream_meta={"face_tag": "front"},
    )


def _refusal(reason_code: str, face_tag: str) -> FieldObservation:
    return FieldObservation(
        field_id=QUALITY_FIELD_ID,
        beverage_class=BeverageClass.SPIRITS,
        observed_value=None,
        evidence=(
            Evidence(
                field_id=QUALITY_FIELD_ID,
                source=EvidenceSource.DERIVED,
                panel=face_tag,
                bbox=None,
                extracted_text=reason_code,
                match_kind=MatchKind.NONE,
                confidence=0.0,
            ),
        ),
        upstream_meta={
            "disposition": "needs_better_photo",
            "reason_code": reason_code,
            "face_tag": face_tag,
        },
    )


def _count_gate_calls(monkeypatch) -> list[object]:
    calls: list[object] = []

    def gate(face):
        calls.append(face)
        return QualityReport(disposition="ok", reason_code=None, dpi=None)

    monkeypatch.setattr("app.services.evaluator.assess_quality", gate)
    return calls


async def _evaluate(observations: list[FieldObservation]):
    evaluator = Evaluator(
        vision=FakeVisionExtractor(observations=observations),
        rules=FakeRuleEngine(results=()),
        settings=Settings(),
    )
    return await evaluator.evaluate(
        application=Application(application_id="A-001", evaluation_id="EV-001"),
        label=_stub_label(),
    )


@pytest.mark.asyncio
async def test_a_reading_is_not_gated_again(monkeypatch):
    calls = _count_gate_calls(monkeypatch)

    await _evaluate([_brand_read()])

    assert calls == [], "the reader gated every face before it read them"


@pytest.mark.asyncio
async def test_the_readers_refusal_stops_the_label_without_a_second_gate(monkeypatch):
    calls = _count_gate_calls(monkeypatch)

    envelope = await _evaluate([_refusal("WARNING.LEGIBILITY.MOTION_BLUR", "back")])

    assert calls == []
    assert envelope.disposition == "needs_review"
    rule_ids = {entry.rule_id for entry in envelope.audit_trail.per_rule_trace}
    assert "WARNING.LEGIBILITY.MOTION_BLUR" in rule_ids


@pytest.mark.asyncio
async def test_a_reader_that_answered_nothing_is_still_gated(monkeypatch):
    calls = _count_gate_calls(monkeypatch)

    await _evaluate([])

    assert len(calls) == 1
