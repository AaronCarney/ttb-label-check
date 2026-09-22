"""Stroke-width measurement for the §16.22(a)(2) bold-heading check.

The measurement is deterministic: it runs on `label.image_bytes` once the layout
call has returned a bbox, and produces a real `is_bold` signal that owes nothing
to a model's judgment.

Algorithm (Otsu + distance-transform + width:height ratio):

  1. Open the heading bbox crop in grayscale.
  2. Otsu's threshold → binary foreground mask of stroke pixels.
  3. Connected components: per-component bounding box gives character height.
  4. Distance transform: per foreground pixel, distance to nearest background;
     mean of positive distances * 2 ≈ mean stroke width per component.
  5. Aggregate: mean(stroke_width) / mean(char_height). Bold when ratio
     exceeds WIDTH_HEIGHT_RATIO_BOLD_MIN.

The measurement is deterministic and repeatable. What it is *not* is a reliable
reading of stroke weight: the corpus sweep below found the ratio
varies more with a photograph's resolution and focus than with the typeface, so
nothing here may reject a label. `WIDTH_HEIGHT_RATIO_BOLD_MIN` carries the
measurement and `docs/decisions.md#0037` carries what was done about it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO

import cv2
import numpy as np
from PIL import Image

_logger = logging.getLogger("app.vision.heading_measure")


WIDTH_HEIGHT_RATIO_BOLD_MIN = 0.25
"""Stroke-width-to-character-height ratio above which the heading is bold.

Set at 0.25 on PIL's default bitmap font, where dilation-merged bold blobs
produce ~0.28 and regular text lands at ~0.22. The re-tune against a labeled
corpus that this comment used to promise has now been run, and it did not
produce a better number -- it showed that no number works.

**Measured over all 38 labels in `tests/fixtures/labels`**, by
`eval/heading_bold_ratios.py`, on the warning-carrying face of each. Every
label in that corpus is TTB-approved, and §16.22(a)(2) requires the heading in
bold, so the whole population should sit above whatever the cut is. It does
not. Of the 30 real labels, 28 measured confidently, and those 28 ran from
0.111 to 0.508 with a median of 0.1995 -- a 4.6x spread across labels that are
all bold, where the difference between bold and regular type is nearer 1.5x.
At 0.25, 18 of the 28 came out below the cut.

The corpus also shows why, without needing the approvals to be taken on trust:
`ttb-26232001000404` measures 0.111, and `var-blur` -- the same printing,
Gaussian-blurred at 2.5 px -- measures 0.261. Same label, same type, 2.3x
apart. `var-glare` measures 0.555, the highest in the corpus. The ratio tracks
resolution, focus and lighting, not stroke weight.

So this number is **no longer a compliance gate**: `heading_style_check` sends
a heading measured below it to a reviewer and never rejects on it
(`docs/decisions.md#0037`). It is kept at 0.25 rather than lowered because,
once it can only choose between passing a label and reviewing it, a low cut
buys a quieter queue by passing headings nobody checked. Raising the reviewer
load is the safe side of a measurement this noisy. Making the ratio mean
something would take normalising it against resolution and print scale, which
is a different piece of work from choosing a threshold."""


@dataclass(frozen=True)
class HeadingMeasurement:
    """Measurement-grade signal for §16.22(a)(2).

    `confident` is False when there was no heading region to measure, or when
    the region held too little ink to produce a meaningful stroke width. The
    other fields are then zero and mean nothing: `is_bold=False` here says
    "not measured", never "measured as not bold". A caller that treats it as
    the latter rejects labels for the reader's blindness."""

    is_bold: bool
    mean_stroke_width: float
    mean_character_height: float
    width_height_ratio: float
    confident: bool


def measure_heading_bold(
    image_bytes: bytes,
    bbox: tuple[int, int, int, int] | None,
) -> HeadingMeasurement:
    """Run the SWT-style measurement on the heading region of encoded bytes.

    `bbox` is `(x0, y0, x1, y1)` in pixel coordinates produced by the layout
    call. It is the heading's own region, and there is no substitute for it:
    with no usable bbox the measurement is not taken, and the result reports
    `confident=False` so the caller knows the boldness was never measured.

    **The bbox and the image must be in the same pixel space.** Nothing here
    rescales: a bbox measured on a downscaled copy, applied to the original,
    crops the wrong part of the label and reports a real stroke width about the
    wrong pixels. A caller that already holds the image the bbox came from
    should pass it to `measure_heading_bold_image` instead of re-encoding it.
    """
    try:
        full = Image.open(BytesIO(image_bytes))
    except Exception:
        return HeadingMeasurement(False, 0.0, 0.0, 0.0, confident=False)

    return measure_heading_bold_image(full, bbox)


def measure_heading_bold_image(
    image: Image.Image,
    bbox: tuple[int, int, int, int] | None,
) -> HeadingMeasurement:
    """The same measurement over an image already in memory.

    The reader computes its boxes on a downscaled copy of the label, so this is
    the entry point that keeps the measurement in the pixel space the bbox was
    measured in. Encoding that copy back to bytes only to decode it again would
    cost a PNG round trip per read and buy nothing.
    """
    try:
        full = image.convert("L")
    except Exception:
        return HeadingMeasurement(False, 0.0, 0.0, 0.0, confident=False)

    crop = _resolve_crop(full, bbox)
    if crop is None:
        return HeadingMeasurement(False, 0.0, 0.0, 0.0, confident=False)

    return _swt_on_crop(crop)


def _resolve_crop(
    full: Image.Image,
    bbox: tuple[int, int, int, int] | None,
) -> Image.Image | None:
    """The heading's own crop, or None when there is no usable region.

    There is deliberately no fallback region. An earlier version measured the
    lower half of the whole image whenever the bbox was missing or degenerate,
    and reported `confident=True` on the result. That crop is most of the
    label: body copy, the mandated statement itself, and whatever else is
    printed down there. Its stroke-width-to-height ratio is a real number
    about the wrong pixels, and a caller told the measurement was confident
    has no way to tell the difference. Since the heading rule now sends an
    unmeasured boldness to a reviewer rather than rejecting the label, the
    honest answer costs nothing and the guess costs a wrong verdict.
    """
    if bbox is None:
        _logger.info(
            "heading_measurement_skipped",
            extra={"reason": "missing_layout_bbox", "image_height": full.height},
        )
        return None
    x0, y0, x1, y1 = bbox
    if x1 <= x0 or y1 <= y0:
        _logger.info(
            "heading_measurement_skipped",
            extra={"reason": "degenerate_layout_bbox", "bbox": bbox},
        )
        return None
    try:
        crop = full.crop((x0, y0, x1, y1))
    except Exception:
        return None
    if crop.width < 8 or crop.height < 8:
        _logger.debug(
            "heading_measurement_skipped",
            extra={
                "reason": "crop_too_small",
                "crop_width": crop.width,
                "crop_height": crop.height,
            },
        )
        return None
    return crop


def _swt_on_crop(crop: Image.Image) -> HeadingMeasurement:
    gray = np.asarray(crop)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # The threshold takes the dark side as ink. A label printing its warning
    # light on dark puts the ground on that side. The ground is what the
    # crop's edges run through, so the side holding most of the edge pixels is
    # the ground whichever way round the label is printed. Counting the whole
    # crop instead fails on heavy capitals cropped tight, where the letters do
    # cover more than half the box.
    edges = np.concatenate([binary[0], binary[-1], binary[:, 0], binary[:, -1]])
    if np.count_nonzero(edges) * 2 > edges.size:
        binary = cv2.bitwise_not(binary)
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)

    widths: list[float] = []
    heights: list[float] = []
    for i in range(1, n_labels):
        x, y, w, h, _area = stats[i]
        comp_dist = dist[y : y + h, x : x + w]
        comp_pixels = comp_dist[comp_dist > 0]
        if comp_pixels.size == 0:
            continue
        widths.append(float(comp_pixels.mean()) * 2.0)
        heights.append(float(h))

    # Component-count floor: blank crops produce zero. Dilated bold text
    # merges into 1-2 blobs, so the floor is 1 (the plan's ≥4 breaks
    # bold+dilation cases). Noise rejection happens via the height floor below.
    if not widths:
        _logger.debug(
            "heading_measurement_unconfident",
            extra={"reason": "no_components", "crop_width": crop.width, "crop_height": crop.height},
        )
        return HeadingMeasurement(False, 0.0, 0.0, 0.0, confident=False)

    mean_w = float(np.mean(widths))
    mean_h = float(np.mean(heights))

    # Height floor: a single dust speck (3-4px tall) can pass the component-
    # count floor but produces a meaningless ratio. Real heading text — even
    # at the lowest fixture resolution we ship — has mean character height
    # ≥ 4px. Below that, defer to the LLM rather than emit a confident
    # measurement on noise.
    if mean_h < 4:
        _logger.debug(
            "heading_measurement_unconfident",
            extra={
                "reason": "mean_height_below_floor",
                "mean_h": round(mean_h, 2),
                "n_components": len(widths),
            },
        )
        return HeadingMeasurement(False, 0.0, 0.0, 0.0, confident=False)

    ratio = mean_w / mean_h if mean_h > 0 else 0.0
    return HeadingMeasurement(
        is_bold=ratio > WIDTH_HEIGHT_RATIO_BOLD_MIN,
        mean_stroke_width=mean_w,
        mean_character_height=mean_h,
        width_height_ratio=ratio,
        confident=True,
    )
