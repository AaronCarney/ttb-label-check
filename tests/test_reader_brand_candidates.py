"""The local reader hands the brand rule every line of text it read.

The brand rule searches the label for the name the application declares, so
it needs the label's text and not only the one line the reader picked. The
reader lists each box, and runs of neighbouring boxes on one line or in one
display block, because a mark is routinely returned as several boxes ("LONE"
beside "RIDER", "Hop" over "Butcher"). Every face's list reaches the rule, since
the name may be printed on a face other than the one whose pick won the merge.
"""

from __future__ import annotations

from app.schemas.expected import BeverageClass
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.vision.faces import merge_readings
from app.vision.local import _Box, _parse, face_observations


def _box(x0: float, y0: float, x1: float, y1: float, text: str, score: float = 0.95) -> _Box:
    return _Box(x0=x0, y0=y0, x1=x1, y1=y1, text=text, score=score)


def _candidates(*boxes: _Box) -> list[dict]:
    payloads = _parse(boxes=list(boxes), warning_boxes=[], rotation=0)
    return payloads["brand_name"][0]["candidates"]


def _texts(candidates: list[dict]) -> list[str]:
    return [c["text"] for c in candidates]


def test_every_box_is_a_candidate() -> None:
    texts = _texts(
        _candidates(
            _box(0, 0, 600, 120, "DISTILLED IN IRELAND"),
            _box(200, 400, 300, 440, "AODH"),
        )
    )
    assert "DISTILLED IN IRELAND" in texts
    assert "AODH" in texts


def test_neighbouring_boxes_on_one_line_are_joined() -> None:
    texts = _texts(
        _candidates(
            _box(0, 100, 200, 160, "LONE"),
            _box(215, 100, 420, 160, "RIDER"),
        )
    )
    assert "LONE RIDER" in texts


def test_lines_of_one_display_block_are_joined_in_reading_order() -> None:
    texts = _texts(
        _candidates(
            _box(100, 100, 300, 180, "Hop"),
            _box(80, 200, 340, 280, "Butcher"),
        )
    )
    assert "Hop Butcher" in texts


def test_a_candidate_carries_its_box_and_score() -> None:
    (candidate,) = [
        c for c in _candidates(_box(10, 20, 110, 60, "AODH", 0.8)) if c["text"] == "AODH"
    ]
    assert candidate["bbox"] == [10, 20, 110, 60]
    assert candidate["confidence"] == 0.8


def test_the_list_holds_each_text_once_in_a_fixed_order() -> None:
    boxes = [
        _box(0, 0, 100, 40, "OAK"),
        _box(0, 300, 100, 340, "OAK"),
        _box(0, 600, 300, 640, "BOTTLED BY OAK SPIRITS"),
    ]
    first = _texts(_candidates(*boxes))
    assert first.count("OAK") == 1
    assert first == _texts(_candidates(*reversed(boxes)))


def test_the_face_is_stamped_on_every_candidate() -> None:
    payloads = _parse(boxes=[_box(0, 0, 200, 60, "AODH")], warning_boxes=[], rotation=0)
    observations = face_observations(payloads, face_tag="back")
    (brand,) = [o for o in observations if o.field_id == "brand_name"]
    assert brand.observed_value["candidates"]
    assert {c["face"] for c in brand.observed_value["candidates"]} == {"back"}


def _brand(panel: str, confidence: float, picked: str, candidates: list[dict]) -> FieldObservation:
    return FieldObservation(
        field_id="brand_name",
        beverage_class=BeverageClass.SPIRITS,
        observed_value={"brand_name": picked, "confidence": confidence, "candidates": candidates},
        evidence=(
            Evidence(
                field_id="brand_name",
                source=EvidenceSource.OCR,
                panel=panel,
                extracted_text=picked,
                match_kind=MatchKind.NONE,
                confidence=confidence,
            ),
        ),
    )


def test_the_merge_carries_every_faces_candidates() -> None:
    """The front's pick wins the merge; the name is printed on the back."""
    front_line = {"text": "BOURBON", "bbox": [0, 0, 9, 9], "confidence": 0.9, "face": "front"}
    back_line = {"text": "AODH", "bbox": [0, 0, 9, 9], "confidence": 0.7, "face": "back"}
    front = [_brand("front", 0.9, "BOURBON", [front_line])]
    back = [_brand("back", 0.5, "AODH", [back_line])]

    (merged,) = merge_readings([front, back])

    assert merged.evidence[0].panel == "front"
    assert merged.observed_value["candidates"] == [front_line, back_line]
