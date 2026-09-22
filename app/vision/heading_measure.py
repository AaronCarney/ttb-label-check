"""Stroke-weight measurement for the §16.22(a)(2) bold-heading check.

27 CFR 16.22(a)(2) requires "GOVERNMENT WARNING" in bold and forbids bold in
the rest of the statement. So every compliant label carries its own
reference: regular type of the same statement, on the same photograph, under
the same blur, glare and resolution. The heading's stroke width is measured
as a ratio to the body's, not against a fixed cut.

Algorithm, run the same way on the heading's crop and on each body line's:

  1. Grayscale crop; Otsu's threshold gives the ink mask, inverted where the
     crop's edges run through the dark side (light type on a dark panel).
  2. Connected components give each letter's height.
  3. A distance transform gives each letter's stroke width: twice the mean
     distance from its ink pixels to the nearest ground.
  4. The heading's median stroke width over the body's is the relative weight.

The measurement is taken only where it can be trusted, and says why where it
was not (`HeadingMeasurement.unmeasured_reason`). A relative weight at or
above `RELATIVE_WEIGHT_BOLD_MIN` is bold. Below it, the measurement cannot
say the heading is regular: some approved labels print a heading that
measures no heavier than its body. `docs/decisions.md#0058` carries the
measurements behind every constant here.
"""

from __future__ import annotations

import logging
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO

import cv2
import numpy as np
from PIL import Image

_logger = logging.getLogger("app.vision.heading_measure")

Bbox = tuple[int, int, int, int]

RELATIVE_WEIGHT_BOLD_MIN = 1.125
"""Heading stroke width over body stroke width at or above which the heading
is bold. The midpoint of the gap on rendered warnings that pass the other
floors here: bold headings measured 1.170 and above, regular headings 1.083
and below. On real photographs, a body line measured against the statement's
other lines reached 1.075."""

LETTER_HEIGHT_MIN_PX = 12.0
"""The heading's median letter height, in pixels of the frame the boxes came
from, below which the weight is not judged. On rendered warnings, bold
headings under 10 px measured no heavier than regular ones; from 10 px to
this floor they cleared the cut by as little as 0.015; at and above it, by
0.045."""

SHARPNESS_MAX = 0.8
"""Mid-grey pixels per ink pixel in the body lines, after stretching each
crop's own contrast, above which the photograph is too blurred to judge.
Blur spreads a stroke's edge into grey on both weights and closes the gap
between them; on rendered warnings at or below this figure the gap held."""

_MIN_LETTERS = 3
"""Components a crop must hold before its median means anything."""

_MIN_BODY_LINES = 2
"""Body lines the reference must span, so one odd line cannot set it."""

_MIN_COMPONENT_HEIGHT_PX = 4
"""Components shorter than this are specks and punctuation, not letters."""


@dataclass(frozen=True)
class HeadingMeasurement:
    """The heading's weight against the warning's own body.

    `confident` is True only when every floor was met. Otherwise
    `unmeasured_reason` says which was not, `is_bold` is False and means
    "not measured", and the widths are whatever was measured before the
    measurement stopped (zero where nothing was).

    With `confident` True, `is_bold` False means "measured, not clearly
    heavier than the body". It is not a finding that the heading is regular.
    """

    is_bold: bool
    relative_weight: float
    heading_stroke_width: float
    body_stroke_width: float
    letter_height: float
    sharpness: float
    confident: bool
    unmeasured_reason: str | None = None


def unmeasured(reason: str, **measured: float) -> HeadingMeasurement:
    """A measurement that was not taken, and why."""
    fields = {
        "relative_weight": 0.0,
        "heading_stroke_width": 0.0,
        "body_stroke_width": 0.0,
        "letter_height": 0.0,
        "sharpness": 0.0,
        **measured,
    }
    return HeadingMeasurement(is_bold=False, confident=False, unmeasured_reason=reason, **fields)


def measure_heading_bold(
    image_bytes: bytes,
    heading_bbox: Bbox | None,
    body_bboxes: Sequence[Bbox] = (),
) -> HeadingMeasurement:
    """The measurement over encoded image bytes.

    The boxes and the image must be in the same pixel space; nothing here
    rescales. A caller that already holds the image the boxes came from should
    pass it to `measure_heading_bold_image` instead of re-encoding it.
    """
    try:
        full = Image.open(BytesIO(image_bytes))
    except Exception:
        return unmeasured("image_unreadable")
    return measure_heading_bold_image(full, heading_bbox, body_bboxes)


def measure_heading_bold_image(
    image: Image.Image,
    heading_bbox: Bbox | None,
    body_bboxes: Sequence[Bbox] = (),
) -> HeadingMeasurement:
    """The heading's weight relative to the body lines, over an image in memory.

    `heading_bbox` is the heading's own characters; `body_bboxes` are the
    statement's lines below it. With no body there is no reference, and the
    weight is not measured.
    """
    try:
        full = image.convert("L")
    except Exception:
        return unmeasured("image_unreadable")

    heading_crop = _crop(full, heading_bbox)
    if heading_crop is None:
        return unmeasured("no_heading_region")
    heading = _letters(heading_crop)
    if len(heading) < _MIN_LETTERS:
        return unmeasured("too_few_heading_letters")
    heading_width = statistics.median(w for w, _h in heading)
    letter_height = statistics.median(h for _w, h in heading)
    if letter_height < LETTER_HEIGHT_MIN_PX:
        return unmeasured(
            "letters_too_small", heading_stroke_width=heading_width, letter_height=letter_height
        )

    body: list[tuple[float, float]] = []
    sharpness: list[float] = []
    lines = 0
    for bbox in body_bboxes:
        crop = _crop(full, bbox)
        if crop is None:
            continue
        letters = _letters(crop)
        if len(letters) < _MIN_LETTERS:
            continue
        lines += 1
        body.extend(letters)
        line_sharpness = _sharpness(crop)
        if line_sharpness is not None:
            sharpness.append(line_sharpness)
    if lines < _MIN_BODY_LINES or not sharpness:
        return unmeasured(
            "too_few_body_lines", heading_stroke_width=heading_width, letter_height=letter_height
        )

    body_width = statistics.median(w for w, _h in body)
    relative = heading_width / body_width
    blur = statistics.median(sharpness)
    measured = {
        "relative_weight": relative,
        "heading_stroke_width": heading_width,
        "body_stroke_width": body_width,
        "letter_height": letter_height,
        "sharpness": blur,
    }
    if blur > SHARPNESS_MAX:
        return unmeasured("too_blurred", **measured)
    return HeadingMeasurement(
        is_bold=relative >= RELATIVE_WEIGHT_BOLD_MIN,
        relative_weight=relative,
        heading_stroke_width=heading_width,
        body_stroke_width=body_width,
        letter_height=letter_height,
        sharpness=blur,
        confident=True,
    )


def _crop(full: Image.Image, bbox: Bbox | None) -> np.ndarray | None:
    """A box's pixels, or None where there is no usable region.

    There is deliberately no fallback region: a measurement of the wrong
    pixels is a real number a caller cannot tell from the right one.
    """
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    if x1 - x0 < 8 or y1 - y0 < 8:
        _logger.debug("heading_measurement_crop_skipped", extra={"bbox": bbox})
        return None
    return np.asarray(full.crop((x0, y0, x1, y1)))


def _ink(gray: np.ndarray) -> tuple[np.ndarray, bool]:
    """The ink mask, and whether the crop was light type on a dark ground.

    The threshold takes the dark side as ink. A label printing its warning
    light on dark puts the ground on that side. The ground is what the crop's
    edges run through, so the side holding most of the edge pixels is the
    ground whichever way round the label is printed. Counting the whole crop
    instead fails on heavy capitals cropped tight, where the letters do cover
    more than half the box.
    """
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    edges = np.concatenate([binary[0], binary[-1], binary[:, 0], binary[:, -1]])
    inverted = np.count_nonzero(edges) * 2 > edges.size
    return (cv2.bitwise_not(binary) if inverted else binary), bool(inverted)


def _letters(gray: np.ndarray) -> list[tuple[float, float]]:
    """Each letter's stroke width and height, in pixels."""
    binary, _inverted = _ink(gray)
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    distance = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    letters = []
    for i in range(1, count):
        x, y, w, h, _area = stats[i]
        if h < _MIN_COMPONENT_HEIGHT_PX:
            continue
        inside = distance[y : y + h, x : x + w]
        inside = inside[inside > 0]
        if inside.size:
            letters.append((float(inside.mean()) * 2.0, float(h)))
    return letters


def _sharpness(gray: np.ndarray) -> float | None:
    """Mid-grey pixels per ink pixel, after stretching the crop's own contrast.

    A sharp print is ink and ground with little between; blur spreads each
    edge into grey. Stretching first makes a faded or low-contrast print read
    by its edges rather than by its ink colour. None where the crop is flat.
    """
    low, high = np.percentile(gray, 2), np.percentile(gray, 98)
    if high - low < 1:
        return None
    stretched = np.clip((gray.astype(float) - low) * 255.0 / (high - low), 0, 255)
    _binary, inverted = _ink(gray)
    if inverted:
        stretched = 255.0 - stretched
    ink = np.count_nonzero(stretched <= 128)
    if not ink:
        return None
    return float(np.count_nonzero((stretched > 64) & (stretched < 192)) / ink)
