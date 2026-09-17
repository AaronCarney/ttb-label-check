"""Reading both faces of a real label, and keeping each field's face with it.

The fault this file guards: the engine read exactly one image per label, so a
bourbon whose government warning is printed on the back was rejected for a
missing warning that nobody had looked for.

No model and no pixels. Both faces are driven from the frozen readings under
`tests/recordings/reader/`, the same recordings `tests/test_vision_replay.py`
scores, so what `_parse` returns here is what the production reader returns on
these two images. Only the step from pixels to boxes is stood in for.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import pytest

from app.config import Settings
from app.schemas.label import Face, Label
from app.vision.local import LocalVisionExtractor, _parse, thaw_reading

# A real approved bourbon from the COLA registry. Its government warning is
# printed on the back and nothing on the front carries one — `warning_image:
# "back"` in `tests/fixtures/labels/manifest.json`.
TTB_ID = "26229001000034"
LABELS = Path("tests/fixtures/labels") / TTB_ID
RECORDINGS = Path("tests/recordings/reader") / TTB_ID


def _reading(face_tag: str):
    return thaw_reading(json.loads((RECORDINGS / f"{face_tag}.json").read_text()))


def _face(face_tag: str) -> Face:
    return Face(
        image_bytes=(LABELS / f"{face_tag}.jpg").read_bytes(),
        content_type="image/jpeg",
        face_tag=face_tag,
    )


@pytest.fixture
def reader(monkeypatch):
    """The production reader with the frozen boxes standing in for the OCR."""
    extractor = LocalVisionExtractor(settings=Settings(), ring_buffer=deque(maxlen=50))
    by_bytes = {_face(tag).image_bytes: tag for tag in ("front", "back")}

    def _frozen(image_bytes: bytes):
        reading = _reading(by_bytes[image_bytes])
        payloads = _parse(
            boxes=reading.boxes,
            warning_boxes=reading.warning_boxes,
            rotation=reading.rotation,
            heading_measurement=reading.heading_measurement,
        )
        return payloads, {
            "reader": "local",
            "engine": "rapidocr",
            "rotation_deg": reading.rotation,
            "boxes_found": len(reading.boxes),
        }

    monkeypatch.setattr(LocalVisionExtractor, "_read_serialised", staticmethod(_frozen))

    async def _loaded(self):
        return None

    monkeypatch.setattr(LocalVisionExtractor, "ensure_loaded", _loaded)
    return extractor


def _label(*face_tags: str) -> Label:
    return Label(
        label_id=TTB_ID,
        batch_id="B-faces",
        faces=tuple(_face(tag) for tag in face_tags),
    )


async def test_the_warning_on_the_back_is_found_when_the_back_is_sent(reader):
    """The whole point of the work: front and back go in, and the warning
    printed on the back comes out."""
    observations = {o.field_id: o for o in await reader.extract(_label("front", "back"))}

    warning = observations["gov_warning"]
    assert warning.evidence[0].confidence > 0.0, "the warning on the back was not read"
    assert "GOVERNMENT WARNING" in (warning.evidence[0].extracted_text or "").upper()


async def test_the_warning_is_absent_when_only_the_front_is_sent(reader):
    """The rule that must keep failing. The same label with only its front
    shows no warning, and the reading says so — `unlocated_is_absent` in
    `rules/common/health_warning.yaml` then fails it, as it should."""
    observations = {o.field_id: o for o in await reader.extract(_label("front"))}

    assert observations["gov_warning"].evidence[0].confidence == 0.0


async def test_every_field_names_the_face_it_was_read_from(reader):
    """Requirement 2: a finding's evidence is traceable to the image it came
    from, which is the moment there is more than one image."""
    observations = await reader.extract(_label("front", "back"))

    assert observations, "the reader returned nothing"
    for obs in observations:
        assert obs.evidence[0].panel in {"front", "back"}, obs.field_id
        assert obs.upstream_meta["face_tag"] == obs.evidence[0].panel

    by_field = {o.field_id: o for o in observations}
    assert by_field["gov_warning"].evidence[0].panel == "back"
    assert by_field["brand_name"].evidence[0].panel == "front"


async def test_one_field_per_face_pair_not_two(reader):
    """Merged, not concatenated. The rule engine runs every applicable rule
    against every observation it is handed, so a second `brand_name` from the
    face that does not show a brand would fail the brand rule on a label whose
    brand is plainly printed on the front."""
    observations = await reader.extract(_label("front", "back"))
    field_ids = [o.field_id for o in observations]

    assert len(field_ids) == len(set(field_ids)), f"duplicate fields: {field_ids}"


async def test_a_single_face_reads_as_it_always_did(reader):
    """No behaviour change for a one-face label, which is every label the
    service has ever been sent."""
    front_only = await reader.extract(_label("front"))
    assert {o.field_id for o in front_only} == {
        "brand_name",
        "class_type",
        "abv",
        "net_contents",
        "gov_warning",
        "name_address",
        "country_origin",
    }
