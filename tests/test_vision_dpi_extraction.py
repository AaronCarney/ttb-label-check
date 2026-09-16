"""Multi-source DPI extraction: PNG pHYs, JPEG EXIF, JFIF, applicant-supplied,
and the signal that says no source resolved.

`assess()` surfaces `dpi=None` when every source is absent, so the rule engine
can attach `ENGINE.MEASUREMENT.MISSING_DPI`. Emitting that code is the rule
engine's job; this suite covers the quality module's half of the contract.

These tests target `_extract_dpi` directly (unit-level over the helper) and round
out an integration assertion through `assess()`. Complementary to the gate-focused
integration coverage in `test_vision_quality_gates.py`.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, TiffImagePlugin

from app.schemas.label import Dimensions, Label
from app.vision.quality import _extract_dpi, assess

FIXTURE = Path("fixtures/01-spirits-clean/label.png")


def _png_with_dpi(dpi: int) -> bytes:
    img = Image.new("RGB", (200, 200), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(dpi, dpi))
    return buf.getvalue()


def _png_without_dpi() -> bytes:
    rng = np.random.default_rng(7)
    arr = (rng.random((200, 200)) * 200).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_with_exif_dpi(dpi: int, *, unit: int = 2) -> bytes:
    """JPEG with EXIF XResolution/YResolution. unit=2 inch, unit=3 cm."""
    rng = np.random.default_rng(8)
    arr = (rng.random((200, 200, 3)) * 200).astype(np.uint8)
    img = Image.fromarray(arr)
    exif = Image.Exif()
    exif[282] = TiffImagePlugin.IFDRational(dpi, 1)
    exif[283] = TiffImagePlugin.IFDRational(dpi, 1)
    exif[296] = unit
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes(), quality=90)
    return buf.getvalue()


def _jpeg_jfif_only(dpi: int) -> bytes:
    """JPEG saved with PIL `dpi=` kwarg → emits JFIF density markers (no EXIF)."""
    rng = np.random.default_rng(9)
    arr = (rng.random((200, 200, 3)) * 200).astype(np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", dpi=(dpi, dpi), quality=90)
    return buf.getvalue()


def test_extract_dpi_from_png_phys():
    assert _extract_dpi(_png_with_dpi(300), None) == 300


def test_extract_dpi_from_jpeg_exif_inches():
    assert _extract_dpi(_jpeg_with_exif_dpi(150), None) == 150


def test_extract_dpi_from_jpeg_exif_cm_converted_to_inch():
    # 118 px/cm ≈ 300 dpi (118 * 2.54 = 299.72 → 300)
    assert _extract_dpi(_jpeg_with_exif_dpi(118, unit=3), None) == 300


def test_extract_dpi_from_jfif_density_marker():
    # PIL collapses JFIF density into info["dpi"] alongside pHYs/EXIF.
    assert _extract_dpi(_jpeg_jfif_only(200), None) == 200


def test_extract_dpi_from_applicant_when_image_metadata_absent():
    dims = Dimensions(width_px=200, height_px=200, dpi=300)
    assert _extract_dpi(_png_without_dpi(), dims) == 300


def test_extract_dpi_none_when_all_sources_missing():
    assert _extract_dpi(_png_without_dpi(), None) is None
    # Also the no-dimensions-at-all case
    assert _extract_dpi(_png_without_dpi(), Dimensions(width_px=200, height_px=200)) is None


def test_assess_surfaces_dpi_none_for_downstream_missing_dpi_signal():
    """When no DPI source resolves, `assess()` returns `dpi=None` so the rule
    engine can attach `ENGINE.MEASUREMENT.MISSING_DPI`. Disposition stays `ok` —
    missing DPI is a measurement-engine concern, not a legibility gate."""
    label = Label(
        label_id="L-MISSING-DPI",
        batch_id="B-001",
        image_bytes=FIXTURE.read_bytes(),  # known-good fixture passes quality gates
        content_type="image/png",
        face_tag="front",
        dimensions=None,
    )
    # The fixture has its own pHYs chunk; strip it by re-encoding without dpi.
    img = Image.open(io.BytesIO(label.image_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")  # no dpi kwarg → no pHYs
    stripped = Label(
        label_id="L-MISSING-DPI",
        batch_id="B-001",
        image_bytes=buf.getvalue(),
        content_type="image/png",
        face_tag="front",
        dimensions=None,
    )
    report = assess(stripped)
    assert report.dpi is None
    assert report.disposition == "ok"
