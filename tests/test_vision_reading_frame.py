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
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.vision.heading_measure import measure_heading_bold
from app.vision.local import MAX_EDGE_PX, LocalVisionExtractor, _Box

FONTS = Path(cv2.__file__).parent / "qt" / "fonts"

_HEADING = "GOVERNMENT WARNING:"
_BODY = (
    "(1) ACCORDING TO THE SURGEON GENERAL, WOMEN SHOULD NOT",
    "DRINK ALCOHOLIC BEVERAGES DURING PREGNANCY BECAUSE",
)
_ORIGINAL = (1800, 2400)


def _label_with_warning_low_on_the_image() -> tuple[bytes, list[tuple[str, tuple]]]:
    """A label wider than the reader's cap, its warning printed low down, and
    each line's text with where it sits in the original's pixels.

    Low down is what makes the two pixel spaces tell different stories: a box
    at y≈0.75 of a 1600px-tall copy is at y≈0.5 of the 2400px original, where
    this label prints nothing at all. The heading is bold over a regular body,
    because the weight is measured against the body.
    """
    regular, bold = (
        ImageFont.truetype(str(FONTS / name), 56)
        for name in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")
    )
    image = Image.new("RGB", _ORIGINAL, color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    lines = [(_HEADING, (60, 1800), bold)] + [
        (text, (60, 1800 + 80 * i), regular) for i, text in enumerate(_BODY, start=1)
    ]
    placed = []
    for text, at, font in lines:
        draw.text(at, text, fill=(0, 0, 0), font=font)
        placed.append((text, draw.textbbox(at, text, font=font)))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), placed


def _scaled(bbox: tuple, scale: float) -> tuple[int, int, int, int]:
    return tuple(int(v * scale) for v in bbox)  # type: ignore[return-value]


def _reader_returning(boxes: list[_Box]) -> LocalVisionExtractor:
    reader = LocalVisionExtractor(settings=Settings(), ring_buffer=deque())
    reader._boxes = lambda image: boxes  # type: ignore[method-assign]
    return reader


def test_heading_boldness_is_measured_where_the_box_actually_is() -> None:
    image_bytes, placed = _label_with_warning_low_on_the_image()
    scale = MAX_EDGE_PX / max(_ORIGINAL)
    boxes = [_Box(*_scaled(bbox, scale), text=text, score=0.95) for text, bbox in placed]

    payloads, _meta = _reader_returning(boxes)._read(image_bytes)
    warning = payloads["gov_warning"][0]

    assert warning["heading_bold_measured_confident"] is True
    assert warning["heading_bold"] is True


def test_the_same_box_against_the_original_measures_the_wrong_pixels() -> None:
    """The defect this closes, kept as a test so it cannot come back quietly.

    The boxes are in the downscaled copy's pixel space. Against the original
    they land on blank paper, and the answer is not "we could not measure" — it
    is a measurement of nothing.
    """
    image_bytes, placed = _label_with_warning_low_on_the_image()
    scale = MAX_EDGE_PX / max(_ORIGINAL)
    heading, *body = (_scaled(bbox, scale) for _text, bbox in placed)

    against_the_original = measure_heading_bold(image_bytes, heading, body)
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
