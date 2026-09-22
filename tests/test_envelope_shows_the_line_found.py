"""A card shows the line a rule found its value on, not only the reader's pick.

The brand rule searches every line read for the application's brand
(`app/rules/_validators/fuzzy_brand.py`). Where the reader's pick is a
statutory line set in larger type and the brand is found on the back, the rule
passes on the back's line. A card that still showed the pick would put
"DISTILLED IN IRELAND IRISH" beside a match against "AODH", with the box drawn
round the wrong text on the wrong photograph.

No pixels and no model: `build_field_findings` is pure.
"""

from __future__ import annotations

from app.schemas.expected import BeverageClass, ExpectedValue
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
from app.services.envelope_builder import build_field_findings

_ENGINE = EngineMeta(
    engine_version="t", rule_pack_version="t", rule_pack="t", started_at_ms=0, elapsed_ms=0
)

_PICK = Evidence(
    field_id="brand_name",
    source=EvidenceSource.OCR,
    panel="front",
    bbox=(0, 0, 400, 80),
    extracted_text="DISTILLED IN IRELAND IRISH",
    match_kind=MatchKind.EXACT,
    confidence=0.95,
)

_FOUND = Evidence(
    field_id="brand_name",
    source=EvidenceSource.OCR,
    panel="back",
    bbox=(40, 300, 160, 340),
    extracted_text="AODH",
    matched_against_value="AODH",
    match_kind=MatchKind.NORMALIZED,
    confidence=0.8,
)


def _observation() -> FieldObservation:
    return FieldObservation(
        field_id="brand_name",
        beverage_class=BeverageClass.SPIRITS,
        observed_value={"brand_name": "DISTILLED IN IRELAND IRISH", "confidence": 0.95},
        evidence=(_PICK,),
    )


def _result(outcome: Outcome, evidence: Evidence) -> ValidationResult:
    return ValidationResult(
        rule_id="spirits.brand.matches_application",
        cfr_citation="27 CFR §5.64",
        beverage_class=BeverageClass.SPIRITS,
        outcome=outcome,
        severity=Severity.WARN,
        reason_code=None if outcome is Outcome.PASS else "BRAND.IDENTIFY.UNCERTAIN",
        evidence=(evidence,),
        aggregated_confidence=evidence.confidence,
        engine_meta=_ENGINE,
    )


def _card(result: ValidationResult):
    (card,) = [
        f
        for f in build_field_findings(
            results=[result],
            observations=[_observation()],
            expected_values=[ExpectedValue(field_id="brand_name", value="AODH")],
        )
        if f.field_name == "brand_name"
    ]
    return card


def test_a_match_found_on_another_line_shows_that_line() -> None:
    card = _card(_result(Outcome.PASS, _FOUND))
    assert card.extracted_value == "AODH"
    assert card.evidence.bbox == (40, 300, 160, 340)
    assert card.evidence.face_tag == "back"
    assert card.evidence.extraction_confidence == 0.8


def test_a_result_sent_to_a_reviewer_shows_the_readers_pick() -> None:
    """Nothing was found, so the card shows what the reader took for the brand
    and the finding's message says the name was not found."""
    card = _card(_result(Outcome.INSUFFICIENT_EVIDENCE, _PICK))
    assert card.extracted_value == "DISTILLED IN IRELAND IRISH"
    assert card.evidence.bbox == (0, 0, 400, 80)
    assert card.evidence.face_tag == "front"
