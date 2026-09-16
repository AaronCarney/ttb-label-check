import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.schemas.label import Dimensions, Label
from app.vision.quality import QualityReport, assess

FIXTURE = Path("fixtures/01-spirits-clean/label.png")


def _png_bytes(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _label(image_bytes: bytes, dpi: int | None = 300) -> Label:
    return Label(
        label_id="L-001",
        batch_id="B-001",
        image_bytes=image_bytes,
        content_type="image/png",
        face_tag="front",
        dimensions=Dimensions(width_px=200, height_px=200, dpi=dpi),
    )


def test_clean_fixture_passes():
    report = assess(_label(FIXTURE.read_bytes()))
    assert report.disposition == "ok"
    assert report.reason_code is None


def test_low_resolution_triggers_warning():
    rng = np.random.default_rng(0)
    arr = (rng.random((64, 64)) * 5 + 125).astype(np.uint8)
    report = assess(_label(_png_bytes(arr)))
    assert report.disposition == "needs_better_photo"
    assert report.reason_code == "WARNING.LEGIBILITY.LOW_RESOLUTION"


def test_glare_triggers_warning():
    rng = np.random.default_rng(1)
    arr = (rng.random((200, 200)) * 100 + 50).astype(np.uint8)
    arr[:100, :100] = 255  # 25% overexposed (>15%)
    report = assess(_label(_png_bytes(arr)))
    assert report.disposition == "needs_better_photo"
    assert report.reason_code == "WARNING.LEGIBILITY.GLARE"


def test_motion_blur_triggers_warning():
    import cv2

    arr = np.full((200, 200), 255, dtype=np.uint8)
    arr[80:120, 30:170] = 0  # text-like dark bar
    kernel = np.zeros((1, 31))
    kernel[0, :] = 1.0 / 31
    streaked = cv2.filter2D(arr, -1, kernel)
    report = assess(_label(_png_bytes(streaked)))
    assert report.disposition == "needs_better_photo"
    assert report.reason_code == "WARNING.LEGIBILITY.MOTION_BLUR"


def _textured_no_meta_png() -> bytes:
    rng = np.random.default_rng(7)
    arr = (rng.random((200, 200)) * 200).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_dpi_from_png_phys():
    # Existing fixture has pHYs chunk → PIL info["dpi"] ≈ (300, 300)
    report = assess(_label(FIXTURE.read_bytes(), dpi=None))
    assert report.dpi == 300


def test_dpi_from_jpeg_exif():
    from PIL import TiffImagePlugin

    img = Image.new("RGB", (200, 200), color=(128, 128, 128))
    # add some texture so quality gates pass
    rng = np.random.default_rng(8)
    arr = (rng.random((200, 200, 3)) * 200).astype(np.uint8)
    img = Image.fromarray(arr)
    exif = Image.Exif()
    exif[282] = TiffImagePlugin.IFDRational(300, 1)
    exif[283] = TiffImagePlugin.IFDRational(300, 1)
    exif[296] = 2  # inches
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes(), quality=90)
    label = Label(
        label_id="L-002",
        batch_id="B-001",
        image_bytes=buf.getvalue(),
        content_type="image/jpeg",
        face_tag="front",
        dimensions=Dimensions(width_px=200, height_px=200, dpi=None),
    )
    report = assess(label)
    assert report.dpi == 300


def test_dpi_from_applicant_when_metadata_absent():
    report = assess(_label(_textured_no_meta_png(), dpi=300))
    assert report.dpi == 300


def test_dpi_none_when_all_sources_missing():
    label = Label(
        label_id="L-003",
        batch_id="B-001",
        image_bytes=_textured_no_meta_png(),
        content_type="image/png",
        face_tag="front",
        dimensions=Dimensions(width_px=200, height_px=200, dpi=None),
    )
    report = assess(label)
    assert report.dpi is None
    assert report.disposition == "ok"
