"""Merging what several faces of one label read.

The question this file settles: a label filed with a front and a back is one
document, so the rules must be run over one reading of it. Hand them both
faces' readings side by side and every rule fires twice — once on the face that
shows the field and once on the face that does not — and the face that does not
is the one that decides, because it fails.
"""

from __future__ import annotations

from app.schemas.expected import BeverageClass
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.vision.faces import QUALITY_FIELD_ID, is_unreadable, merge_readings


def _obs(field_id: str, *, panel: str, confidence: float, text: str = "") -> FieldObservation:
    return FieldObservation(
        field_id=field_id,
        beverage_class=BeverageClass.SPIRITS,
        observed_value={"confidence": confidence, "text": text},
        evidence=(
            Evidence(
                field_id=field_id,
                source=EvidenceSource.OCR,
                panel=panel,
                bbox=None,
                extracted_text=text,
                match_kind=MatchKind.NONE,
                confidence=confidence,
            ),
        ),
    )


def test_each_field_comes_from_the_face_that_shows_it():
    """The bourbon this work exists for: brand on the front, warning on the
    back, and one reading that carries both."""
    front = [
        _obs("brand_name", panel="front", confidence=0.93, text="OLD FENCEPOST"),
        _obs("gov_warning", panel="front", confidence=0.0),
    ]
    back = [
        _obs("brand_name", panel="back", confidence=0.0),
        _obs("gov_warning", panel="back", confidence=0.88, text="GOVERNMENT WARNING: ..."),
    ]
    merged = {o.field_id: o for o in merge_readings([front, back])}

    assert len(merged) == 2, "one observation per field, not one per face"
    assert merged["brand_name"].evidence[0].panel == "front"
    assert merged["brand_name"].evidence[0].extracted_text == "OLD FENCEPOST"
    assert merged["gov_warning"].evidence[0].panel == "back"
    assert merged["gov_warning"].evidence[0].extracted_text == "GOVERNMENT WARNING: ..."


def test_a_field_no_face_shows_stays_absent():
    """The rule that must keep failing. A warning printed on neither submitted
    face reaches the rules as the absent reading it is, and 16.21 fails on it
    exactly as it does today."""
    front = [_obs("gov_warning", panel="front", confidence=0.0)]
    back = [_obs("gov_warning", panel="back", confidence=0.0)]
    merged = merge_readings([front, back])

    assert len(merged) == 1
    assert merged[0].field_id == "gov_warning"
    assert merged[0].evidence[0].confidence == 0.0


def test_ties_go_to_the_earlier_face():
    """Faces are held in the order they were submitted, and the front is sent
    first, so a field both faces read equally well is reported from the front."""
    front = [_obs("brand_name", panel="front", confidence=0.7, text="FRONT")]
    back = [_obs("brand_name", panel="back", confidence=0.7, text="BACK")]
    merged = merge_readings([front, back])

    assert merged[0].evidence[0].panel == "front"


def test_one_face_merges_to_itself():
    """A label with a single face reads exactly as it did before there were
    faces at all."""
    front = [
        _obs("brand_name", panel="front", confidence=0.9, text="OLD FENCEPOST"),
        _obs("gov_warning", panel="front", confidence=0.4),
    ]
    assert merge_readings([front]) == front


def test_field_order_follows_first_appearance():
    front = [_obs("brand_name", panel="front", confidence=0.9)]
    back = [
        _obs("brand_name", panel="back", confidence=0.95),
        _obs("gov_warning", panel="back", confidence=0.9),
    ]
    assert [o.field_id for o in merge_readings([front, back])] == ["brand_name", "gov_warning"]


def test_a_refused_face_is_recognised_as_a_refusal():
    refusal = [
        FieldObservation(
            field_id=QUALITY_FIELD_ID,
            beverage_class=BeverageClass.SPIRITS,
            observed_value=None,
            evidence=(
                Evidence(
                    field_id=QUALITY_FIELD_ID,
                    source=EvidenceSource.DERIVED,
                    panel="back",
                    bbox=None,
                    extracted_text="WARNING.LEGIBILITY.MOTION_BLUR",
                    match_kind=MatchKind.NONE,
                    confidence=0.0,
                ),
            ),
        )
    ]
    assert is_unreadable(refusal)
    assert not is_unreadable([_obs("brand_name", panel="front", confidence=0.0)])
