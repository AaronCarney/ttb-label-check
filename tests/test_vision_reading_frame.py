"""The heading is measured on the frame its box was measured in.

The reader shrinks a big label to `MAX_EDGE_PX` and finds its boxes on that
copy. The boldness measurement crops a box out of an image and does not
rescale, so it has to be handed the same copy. Handed the original instead, it
crops a different part of the label and reports a real stroke-width number
about the wrong pixels — usually confidently, which is the part that reaches a
reviewer as a measured fact.

No OCR engine runs here: the box list the engine would return is supplied
directly, which is the only part of the reading these tests are about.
"""
from __future__ import annotations

from collections import deque
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.vision.heading_measure import measure_heading_bold
from app.vision.local import MAX_EDGE_PX, _Box, LocalVisionExtractor

_HEADING = "GOVERNMENT WARNING:"


def _label_with_heading_low_on_the_image() -> bytes:
    """A label wider than the reader's cap, its heading printed low down.

    Low down is what makes the two pixel spaces tell different stories: a box
    at y≈0.75 of a 1600px-tall copy is at y≈0.5 of the 2400px original, where
    this label prints nothing at all.
    """
    image = Image.new("RGB", (1800, 2400), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(90)
    except TypeError:  # pragma: no cover — older PIL, fixed size only
        font = ImageFont.load_default()
    draw.text((120, 1800), _HEADING, fill=(0, 0, 0), font=font, stroke_width=12)  # bold enough to read as bold
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _ink_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    """Where the ink sits in the image handed in, with a little margin."""
    ink = np.asarray(image.convert("L")) < 128
    ys, xs = np.nonzero(ink)
    return (int(xs.min()) - 4, int(ys.min()) - 4, int(xs.max()) + 4, int(ys.max()) + 4)


def _thumbnail(image_bytes: bytes) -> Image.Image:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    if max(image.size) > MAX_EDGE_PX:
        image.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX))
    return image


def _reader_returning(box: _Box) -> LocalVisionExtractor:
    reader = LocalVisionExtractor(settings=Settings(), ring_buffer=deque())
    reader._boxes = lambda image: [box]  # type: ignore[method-assign]
    return reader


def test_heading_boldness_is_measured_where_the_box_actually_is() -> None:
    image_bytes = _label_with_heading_low_on_the_image()
    bbox = _ink_bbox(_thumbnail(image_bytes))
    box = _Box(x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3], text=_HEADING, score=0.95)

    payloads, _meta = _reader_returning(box)._read(image_bytes)
    warning = payloads["gov_warning"][0]

    assert warning["heading_bold_measured_confident"] is True
    assert warning["heading_bold"] is True


def test_the_same_box_against_the_original_measures_the_wrong_pixels() -> None:
    """The defect this closes, kept as a test so it cannot come back quietly.

    The box is in the downscaled copy's pixel space. Against the original it
    lands on blank paper, and the answer is not "we could not measure" — it is
    a measurement of nothing.
    """
    image_bytes = _label_with_heading_low_on_the_image()
    bbox = _ink_bbox(_thumbnail(image_bytes))

    against_the_original = measure_heading_bold(image_bytes, bbox)
    assert not against_the_original.confident


def test_parse_needs_no_image_at_all() -> None:
    """`_parse` is a pure function of the boxes, which is what makes a frozen
    reading replayable with no image, no model and no network."""
    import inspect

    from app.vision.local import _parse

    parameters = inspect.signature(_parse).parameters
    assert "warning_image_bytes" not in parameters
    assert set(parameters) == {"boxes", "warning_boxes", "rotation", "heading_measurement"}

    payloads = _parse(
        boxes=[_Box(10, 10, 200, 40, _HEADING, 0.9)],
        warning_boxes=[_Box(10, 10, 200, 40, _HEADING, 0.9)],
        rotation=0,
    )
    assert payloads["gov_warning"][0]["heading_all_caps"] is True
    assert payloads["gov_warning"][0]["heading_bold_measured_confident"] is False
