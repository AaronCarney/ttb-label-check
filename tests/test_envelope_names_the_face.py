"""Which photograph a finding was read from, all the way to the wire.

The fault this file guards: the reader has named the face on every piece of
evidence since the two-face work landed (`Evidence.panel`,
`upstream_meta["face_tag"]`), and `app/services/envelope_builder.py` dropped
both when it built the wire envelope. A reviewer then saw a government-warning
finding beside two photographs with nothing joining the one to the other.

No pixels and no model: `build_field_findings` is pure, so the observations are
built here by hand in the shape the readers produce.
"""

from __future__ import annotations

from app.schemas.expected import BeverageClass, ExpectedValue
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
from app.services.envelope_builder import build_field_findings

_ENGINE = EngineMeta(
    engine_version="t", rule_pack_version="t", rule_pack="t", started_at_ms=0, elapsed_ms=0
)


def _observation(field_id: str, *, panel: str | None, text: str) -> FieldObservation:
    return FieldObservation(
        field_id=field_id,
        beverage_class=BeverageClass.SPIRITS,
        observed_value=text,
        evidence=(
            Evidence(
                field_id=field_id,
                source=EvidenceSource.OCR,
                panel=panel,
                bbox=(0, 0, 10, 10),
                extracted_text=text,
                match_kind=MatchKind.EXACT,
                confidence=0.9,
            ),
        ),
        upstream_meta={"face_tag": panel} if panel else {},
    )


def _passing_rule(field_id: str) -> ValidationResult:
    return ValidationResult(
        rule_id=f"common.{field_id}.present",
        cfr_citation="27 CFR §5.63",
        beverage_class=BeverageClass.SPIRITS,
        outcome=Outcome.PASS,
        severity=Severity.INFO,
        reason_code="OK",
        message="ok",
        evidence=(
            Evidence(
                field_id=field_id,
                source=EvidenceSource.OCR,
                match_kind=MatchKind.EXACT,
                confidence=0.9,
            ),
        ),
        aggregated_confidence=0.9,
        engine_meta=_ENGINE,
    )


def _findings(observations):
    return {
        f.field_name: f
        for f in build_field_findings(
            results=[_passing_rule(o.field_id) for o in observations],
            observations=observations,
            expected_values=[
                ExpectedValue(field_id=o.field_id, value=o.observed_value) for o in observations
            ],
        )
    }


def test_each_field_carries_the_face_it_was_read_from():
    """The brand is on the front, the warning is on the back, and the envelope
    says so — which is what lets a card tell the reviewer which photograph to
    look at."""
    findings = _findings(
        [
            _observation("brand_name", panel="front", text="Lucky Lucy's"),
            _observation("gov_warning", panel="back", text="GOVERNMENT WARNING: ..."),
        ]
    )

    assert findings["brand_name"].evidence.face_tag == "front"
    assert findings["warning"].evidence.face_tag == "back"


def test_a_reading_that_names_no_face_says_nothing_rather_than_guessing():
    """Evidence with no panel is evidence that did not record a face — a
    hand-built fixture, or a reader that predates the field. Empty is the
    honest answer; naming the front would be a guess, and the front is exactly
    where a warning finding is not."""
    findings = _findings([_observation("brand_name", panel=None, text="Lucky Lucy's")])

    assert findings["brand_name"].evidence.face_tag == ""
