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

This is uncalibrated against a labeled corpus: the threshold started at 0.30 and
works on the demo fixtures. A tighter cut belongs in the same sweep over real
labels that settles the image-quality and brand-match thresholds.
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
Lowered from 0.30: dilation-merged bold blobs produce ratios ~0.28 on
PIL's default bitmap font. Regular text without dilation lands at ~0.22.
Empirical re-tune against a labeled corpus is still to come."""


@dataclass(frozen=True)
class HeadingMeasurement:
    """Measurement-grade signal for §16.22(a)(2). `confident` is False when the
    crop was empty or too small to produce a meaningful component count, in
    which case downstream code should fall back to the LLM's `heading_bold`."""

    is_bold: bool
    mean_stroke_width: float
    mean_character_height: float
    width_height_ratio: float
    confident: bool


def measure_heading_bold(
    image_bytes: bytes,
    bbox: tuple[int, int, int, int] | None,
) -> HeadingMeasurement:
    """Run the SWT-style measurement on the heading region.

    `bbox` is `(x0, y0, x1, y1)` in pixel coordinates produced by the layout
    call. A `None` or zero-area bbox triggers a fallback: measure the lower
    half of the full image, where the §16.22 warning heading lives by
    regulation. The fallback only reports `confident=True` when there are
    enough connected components to produce a stable stroke-width estimate.
    """
    try:
        full = Image.open(BytesIO(image_bytes)).convert("L")
    except Exception:  # noqa: BLE001 — defensive: malformed PNG
        return HeadingMeasurement(False, 0.0, 0.0, 0.0, confident=False)

    crop = _resolve_crop(full, bbox)
    if crop is None:
        return HeadingMeasurement(False, 0.0, 0.0, 0.0, confident=False)

    return _swt_on_crop(crop)


def _resolve_crop(
    full: "Image.Image",
    bbox: tuple[int, int, int, int] | None,
) -> "Image.Image | None":
    """Return the actual crop to measure, or None if no usable region."""
    if bbox is not None:
        x0, y0, x1, y1 = bbox
        if x1 > x0 and y1 > y0:
            try:
                crop = full.crop((x0, y0, x1, y1))
            except Exception:  # noqa: BLE001
                return None
            if crop.width >= 8 and crop.height >= 8:
                return crop
    # Fallback: the lower half of the image. §16.22(a) places the warning at
    # the bottom of the label, so this is where the heading text lives.
    h = full.height
    if h < 16:
        return None
    # Logged at info because operating without a real bbox is the GPT-4o
    # layout-call failure mode this fallback exists for; an ops dashboard
    # tracking how often this fires gives an early signal that the layout
    # prompt has regressed.
    _logger.info(
        "heading_bbox_fallback_to_lower_half",
        extra={
            "reason": "degenerate_layout_bbox" if bbox is not None else "missing_layout_bbox",
            "image_height": h,
            "image_width": full.width,
        },
    )
    return full.crop((0, h // 2, full.width, h))


def _swt_on_crop(crop: "Image.Image") -> HeadingMeasurement:
    gray = np.asarray(crop)
    _, binary = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
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
