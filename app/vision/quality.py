"""Vision quality gates — assess label image and emit warnings or pass-through.

Gates: low-resolution (Laplacian variance), motion blur (FFT high-frequency
energy ratio), DPI extraction (EXIF/pHYs/JFIF/applicant).

There is no glare gate. One stood here and counted the pixels brighter than
240: over 15% of them, on an image whose median was not itself that bright,
returned WARNING.LEGIBILITY.GLARE. That statistic measures how light the label
stock is, not whether glare destroyed any text, because an unprinted white area
and a blown-out one are the same pixel values. On the 30 real labels it turned
away seven faces of five labels that are sharp and perfectly readable — two of
them on both faces, so those labels were scored against no reading at all —
while passing `var-glare`, the fixture built with a hotspot over its warning,
and turning away `var-skew`, which has no glare on it. No threshold fixes that:
what a hotspot covered is not knowable before the label is read. Legibility is
now judged by what the reader returned, in `app/vision/local.py`: an image that
yields no text at all is the image nobody can check.
"""

from __future__ import annotations

import io
from typing import Literal

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict

from app.schemas.label import Dimensions, Label

LOW_RES_VARIANCE_MIN = 50.0
MOTION_BLUR_HIGHFREQ_MIN = 0.30

_EXIF_X_RESOLUTION = 282
_EXIF_Y_RESOLUTION = 283
_EXIF_RESOLUTION_UNIT = 296  # 2=inch, 3=cm


class QualityReport(BaseModel):
    """Outcome of vision quality assessment for a single label."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    disposition: Literal["ok", "needs_better_photo"]
    reason_code: str | None
    dpi: int | None


def _decode_grayscale(image_bytes: bytes) -> np.ndarray | None:
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
    except (UnidentifiedImageError, OSError, Exception):
        return None
    return np.array(img)


def _highfreq_ratio(gray: np.ndarray) -> float:
    f = np.fft.fft2(gray.astype(np.float64))
    fshift = np.fft.fftshift(f)
    mag = np.abs(fshift)
    h, w = gray.shape
    cy, cx = h // 2, w // 2
    radius = min(h, w) // 8
    Y, X = np.ogrid[:h, :w]
    high_mask = np.sqrt((Y - cy) ** 2 + (X - cx) ** 2) > radius
    total = mag.sum()
    return float(mag[high_mask].sum() / total) if total > 0 else 0.0


def _extract_dpi(image_bytes: bytes, dimensions: Dimensions | None) -> int | None:
    """Try sources in order: PIL info["dpi"] (PNG pHYs / JFIF) → EXIF
    XResolution/YResolution → applicant Dimensions.dpi → None."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except (UnidentifiedImageError, OSError, Exception):
        if dimensions is not None and dimensions.dpi is not None:
            return dimensions.dpi
        return None

    info_dpi = img.info.get("dpi")
    if info_dpi:
        x = float(info_dpi[0])
        if x > 0:
            return round(x)

    exif = img.getexif()
    x_res = exif.get(_EXIF_X_RESOLUTION)
    if x_res:
        unit = exif.get(_EXIF_RESOLUTION_UNIT, 2)
        x_val = float(x_res)
        if x_val > 0:
            if unit == 3:  # cm → convert to inch
                x_val *= 2.54
            return round(x_val)

    if dimensions is not None and dimensions.dpi is not None:
        return dimensions.dpi

    return None


def assess(label: Label) -> QualityReport:
    """Run vision quality gates against a Label and return a QualityReport."""
    gray = _decode_grayscale(label.image_bytes)
    dpi = _extract_dpi(label.image_bytes, label.dimensions)

    if gray is None:
        return QualityReport(
            disposition="needs_better_photo",
            reason_code="WARNING.LEGIBILITY.LOW_RESOLUTION",
            dpi=dpi,
        )

    if cv2.Laplacian(gray, cv2.CV_64F).var() < LOW_RES_VARIANCE_MIN:
        return QualityReport(
            disposition="needs_better_photo",
            reason_code="WARNING.LEGIBILITY.LOW_RESOLUTION",
            dpi=dpi,
        )

    if _highfreq_ratio(gray) < MOTION_BLUR_HIGHFREQ_MIN:
        return QualityReport(
            disposition="needs_better_photo",
            reason_code="WARNING.LEGIBILITY.MOTION_BLUR",
            dpi=dpi,
        )

    return QualityReport(disposition="ok", reason_code=None, dpi=dpi)
