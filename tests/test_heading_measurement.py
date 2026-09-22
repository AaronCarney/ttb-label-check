"""The heading's weight is measured against the warning's own body.

The warnings here are rendered in real type — the DejaVu faces opencv-python
ships, regular and bold, normal and condensed — and measured through the
reader's own `_measure_heading`, with the boxes an OCR engine returns for a
warning. `eval/heading_bold_ratios.py` holds the renderer and the study the
constants in `app/vision/heading_measure.py` were set on.

The case that matters most is the first: a regular heading over a regular
body must never measure bold, however the photograph is degraded, because a
false "bold" passes a label nobody checked. Every other failure of the
measurement sends the label to a reviewer, which costs time and nothing else.
"""

from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from app.vision.heading_measure import (
    LETTER_HEIGHT_MIN_PX,
    RELATIVE_WEIGHT_BOLD_MIN,
    measure_heading_bold,
    measure_heading_bold_image,
)
from app.vision.local import _measure_heading
from eval.heading_bold_ratios import BLURS, DEGRADES, FACES, SIZES, RenderedWarning, measure, render


def test_a_regular_heading_over_a_regular_body_is_never_bold() -> None:
    """Every face, size 10 to 34, blur 0 to 3, JPEG quality 20 and half
    resolution, light on dark and lower case: not one is called bold."""
    called_bold = [
        (w, round(m.relative_weight, 3))
        for face in FACES
        for size in SIZES
        for blur in BLURS
        for degrade in DEGRADES
        for invert in (False, True)
        for lower in (False, True)
        for w in [RenderedWarning(face, size, "regular-heading", lower, blur, invert, degrade)]
        for m in [measure(w)]
        if m.is_bold
    ]
    assert not called_bold


@pytest.mark.parametrize("face", list(FACES))
@pytest.mark.parametrize("size", [16, 20, 26, 34])
@pytest.mark.parametrize("invert", [False, True])
def test_a_bold_heading_in_a_sharp_photo_is_bold(face: str, size: int, invert: bool) -> None:
    measurement = measure(RenderedWarning(face, size, "bold-heading", invert=invert))

    assert measurement.confident, measurement.unmeasured_reason
    assert measurement.letter_height >= LETTER_HEIGHT_MIN_PX
    assert measurement.is_bold
    assert measurement.relative_weight >= RELATIVE_WEIGHT_BOLD_MIN


def test_small_type_is_not_judged() -> None:
    measurement = measure(RenderedWarning(size=12, kind="bold-heading"))

    assert measurement.letter_height < LETTER_HEIGHT_MIN_PX
    assert not measurement.confident
    assert not measurement.is_bold
    assert measurement.unmeasured_reason == "letters_too_small"


def test_a_heavily_blurred_photo_is_not_judged() -> None:
    measurement = measure(RenderedWarning(size=34, kind="bold-heading", blur=2.0))

    assert not measurement.confident
    assert measurement.unmeasured_reason == "too_blurred"


def test_a_heading_with_no_body_beneath_it_is_not_judged() -> None:
    """With no body there is nothing to measure the heading against."""
    frame, boxes = render(RenderedWarning(size=26, kind="bold-heading"))

    measurement = _measure_heading(frame, boxes[:1])

    assert measurement is not None
    assert not measurement.confident
    assert measurement.unmeasured_reason == "too_few_body_lines"


def test_a_warning_printed_all_in_bold_is_not_called_bold_on_a_capital_body() -> None:
    """§16.22(a)(2) forbids bold in the body. A body as heavy as the heading
    gives the heading nothing to stand out against, so it is not called bold
    and the weight goes to a reviewer."""
    measurement = measure(RenderedWarning(size=26, kind="all-bold"))

    assert measurement.confident
    assert not measurement.is_bold


def test_light_type_on_a_dark_ground_measures_the_same() -> None:
    """The threshold takes the dark side as ink; a label printing its warning
    light on dark puts the ground there, and the measurement must turn round."""
    dark_on_light = measure(RenderedWarning(size=26, kind="bold-heading"))
    light_on_dark = measure(RenderedWarning(size=26, kind="bold-heading", invert=True))

    assert light_on_dark == dark_on_light


def test_the_heading_crop_stops_short_of_the_statement_sharing_its_box() -> None:
    """The engine returns the heading and the start of the statement as one
    box. Measuring the whole box would count regular type as the heading."""
    w = RenderedWarning(size=26, kind="bold-heading")
    frame, boxes = render(w)
    whole_box = boxes[0]
    body = [b.as_bbox() for b in boxes[1:]]

    cut = measure(w)
    uncut = measure_heading_bold_image(frame, whole_box.as_bbox(), body)

    assert cut.relative_weight > uncut.relative_weight


def _png(gray: np.ndarray) -> bytes:
    out = BytesIO()
    Image.fromarray(gray.astype(np.uint8), mode="L").save(out, "PNG")
    return out.getvalue()


def test_no_heading_box_is_no_measurement() -> None:
    """A missing box is the reader's failure, not evidence about the label.
    There is no fallback region: a measurement of the wrong pixels is a real
    number a caller cannot tell from the right one."""
    frame, boxes = render(RenderedWarning(size=26))
    buffer = BytesIO()
    frame.save(buffer, format="PNG")
    body = [b.as_bbox() for b in boxes[1:]]

    for heading in (None, (0, 0, 0, 0), (0, 0, 4, 4)):
        measurement = measure_heading_bold(buffer.getvalue(), heading, body)
        assert not measurement.confident
        assert not measurement.is_bold
        assert measurement.relative_weight == 0.0
        assert measurement.unmeasured_reason == "no_heading_region"


def test_blank_paper_and_a_speck_are_not_a_heading() -> None:
    blank = np.full((80, 200), 255)
    speck = blank.copy()
    speck[40:43, 100:103] = 0

    for image in (blank, speck):
        measurement = measure_heading_bold(_png(image), (10, 10, 190, 70), [(0, 0, 200, 80)] * 2)
        assert not measurement.confident
        assert measurement.unmeasured_reason == "too_few_heading_letters"


def test_an_unreadable_image_is_no_measurement() -> None:
    measurement = measure_heading_bold(b"not an image", (0, 0, 10, 10))

    assert not measurement.confident
    assert measurement.unmeasured_reason == "image_unreadable"


def test_the_measurement_is_the_same_every_time() -> None:
    w = RenderedWarning(face="dejavu-condensed", size=20, kind="bold-heading", degrade="jpeg20")

    assert measure(w) == measure(replace(w))
