import pytest
from pydantic import ValidationError

from app.schemas.label import Dimensions, Label


def test_label_round_trip():
    label = Label(
        label_id="L-001",
        batch_id="B-001",
        image_bytes=b"\x89PNG\r\n\x1a\n",
        content_type="image/png",
        face_tag="front",
        dimensions=Dimensions(width_px=200, height_px=200, dpi=300),
    )
    assert label.label_id == "L-001"
    assert label.dimensions.dpi == 300


def test_label_frozen():
    label = Label(
        label_id="L-001",
        batch_id="B-001",
        image_bytes=b"x",
        content_type="image/jpeg",
        face_tag="front",
        dimensions=None,
    )
    with pytest.raises(ValidationError):
        label.label_id = "L-002"


def test_label_extra_forbidden():
    with pytest.raises(ValidationError):
        Label(
            label_id="L-001",
            batch_id="B-001",
            image_bytes=b"x",
            content_type="image/jpeg",
            face_tag="front",
            dimensions=None,
            unknown_field="x",
        )


def test_label_content_type_restricted():
    with pytest.raises(ValidationError):
        Label(
            label_id="L-001",
            batch_id="B-001",
            image_bytes=b"x",
            content_type="image/gif",  # not in JPEG/PNG allowlist
            face_tag="front",
            dimensions=None,
        )


def test_label_face_tag_restricted():
    with pytest.raises(ValidationError):
        Label(
            label_id="L-001",
            batch_id="B-001",
            image_bytes=b"x",
            content_type="image/png",
            face_tag="bottom",  # not in {front, back, neck, side}
            dimensions=None,
        )
