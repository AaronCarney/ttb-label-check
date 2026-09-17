import pytest
from pydantic import ValidationError

from app.schemas.label import Dimensions, Face, Label


def _face(**overrides) -> Face:
    kwargs = {
        "image_bytes": b"\x89PNG\r\n\x1a\n",
        "content_type": "image/png",
        "face_tag": "front",
        "dimensions": Dimensions(width_px=200, height_px=200, dpi=300),
    }
    kwargs.update(overrides)
    return Face(**kwargs)


def test_label_round_trip():
    label = Label(label_id="L-001", batch_id="B-001", faces=(_face(),))
    assert label.label_id == "L-001"
    assert label.faces[0].dimensions.dpi == 300


def test_label_carries_every_face_in_order():
    """A label is a document and its faces are its pages, so the order they
    were sent in is the order they are held in."""
    front = _face(face_tag="front", image_bytes=b"front-bytes")
    back = _face(face_tag="back", image_bytes=b"back-bytes")
    label = Label(label_id="L-001", batch_id="B-001", faces=(front, back))
    assert [f.face_tag for f in label.faces] == ["front", "back"]


def test_label_needs_at_least_one_face():
    """A label with no image is nothing to read, so it is not a label."""
    with pytest.raises(ValidationError):
        Label(label_id="L-001", batch_id="B-001", faces=())


def test_label_frozen():
    label = Label(label_id="L-001", batch_id="B-001", faces=(_face(),))
    with pytest.raises(ValidationError):
        label.label_id = "L-002"


def test_face_frozen():
    face = _face()
    with pytest.raises(ValidationError):
        face.face_tag = "back"


def test_label_extra_forbidden():
    with pytest.raises(ValidationError):
        Label(label_id="L-001", batch_id="B-001", faces=(_face(),), unknown_field="x")


def test_face_extra_forbidden():
    with pytest.raises(ValidationError):
        _face(unknown_field="x")


def test_face_content_type_restricted():
    with pytest.raises(ValidationError):
        _face(content_type="image/gif")  # not in JPEG/PNG allowlist


def test_face_tag_restricted():
    with pytest.raises(ValidationError):
        _face(face_tag="bottom")  # not in {front, back, neck, side}
