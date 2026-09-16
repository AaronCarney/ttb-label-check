"""Tests for app/vision/heading_measure.py — local SWT-style bold detector."""
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.vision.heading_measure import (
    WIDTH_HEIGHT_RATIO_BOLD_MIN,
    measure_heading_bold,
)


def _png_text(text: str, size: int, weight: str) -> bytes:
    """Render `text` at the given pixel size with either bold or regular
    weight using PIL's default bitmap font (regular) or a synthetic bold via
    cv2 morphological dilation. Returns PNG bytes for SWT input."""
    import cv2
    img = Image.new("L", (260, 80), color=255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size)
    except TypeError:
        font = ImageFont.load_default()
    draw.text((10, 10), text, fill=0, font=font)
    arr = np.asarray(img)
    if weight == "bold":
        ink = (arr < 128).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        ink = cv2.dilate(ink, kernel, iterations=2)
        arr = np.where(ink > 0, 0, 255).astype(np.uint8)
    out = BytesIO()
    Image.fromarray(arr, mode="L").save(out, "PNG")
    return out.getvalue()


def test_bold_text_classified_as_bold():
    """Heavy strokes -> width:height ratio above the threshold."""
    bbox = (0, 0, 260, 80)
    png = _png_text("GOVERNMENT WARNING", size=24, weight="bold")
    m = measure_heading_bold(png, bbox)
    assert m.confident
    assert m.is_bold
    assert m.width_height_ratio > WIDTH_HEIGHT_RATIO_BOLD_MIN


def test_regular_text_classified_as_not_bold():
    """Default weight strokes -> ratio below the threshold."""
    bbox = (0, 0, 260, 80)
    png = _png_text("GOVERNMENT WARNING", size=12, weight="regular")
    m = measure_heading_bold(png, bbox)
    assert m.confident
    assert not m.is_bold
    assert m.width_height_ratio <= WIDTH_HEIGHT_RATIO_BOLD_MIN


def test_zero_bbox_returns_unconfident_when_no_text_present():
    """A degenerate bbox + a blank lower half can't be measured."""
    blank = Image.new("L", (200, 80), color=255)
    out = BytesIO()
    blank.save(out, "PNG")
    m = measure_heading_bold(out.getvalue(), (0, 0, 0, 0))
    assert not m.confident


def test_none_bbox_returns_unconfident_when_no_text_present():
    blank = Image.new("L", (200, 80), color=255)
    out = BytesIO()
    blank.save(out, "PNG")
    m = measure_heading_bold(out.getvalue(), None)
    assert not m.confident


def test_tiny_crop_returns_unconfident():
    """A crop smaller than 8x8 pixels can't host enough components."""
    png = _png_text("GOVERNMENT WARNING", size=24, weight="bold")
    m = measure_heading_bold(png, (0, 0, 4, 4))
    assert not m.confident


def test_zero_bbox_falls_back_to_lower_half_when_text_present():
    """GPT-4o's layout call sometimes returns [0,0,0,0]. The measurement
    must still run on a sensible region rather than punting to the LLM —
    the heading lives in the lower half of TTB labels by regulation, so
    that's the fallback crop."""
    # 200x80 image: top half is white, bottom half has rendered bold text.
    img = Image.new("L", (200, 80), color=255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(24)
    except TypeError:
        font = ImageFont.load_default()
    draw.text((10, 50), "GOVERNMENT WARNING", fill=0, font=font)
    arr = np.asarray(img)
    import cv2
    ink = (arr < 128).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    ink = cv2.dilate(ink, kernel, iterations=2)
    arr = np.where(ink > 0, 0, 255).astype(np.uint8)
    out = BytesIO()
    Image.fromarray(arr, mode="L").save(out, "PNG")
    png = out.getvalue()

    m = measure_heading_bold(png, (0, 0, 0, 0))
    assert m.confident, "fallback must run when bbox is degenerate"
    assert m.is_bold


def test_none_bbox_falls_back_to_lower_half():
    img = Image.new("L", (200, 80), color=255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(24)
    except TypeError:
        font = ImageFont.load_default()
    draw.text((10, 50), "GOVERNMENT WARNING", fill=0, font=font)
    arr = np.asarray(img)
    import cv2
    ink = (arr < 128).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    ink = cv2.dilate(ink, kernel, iterations=2)
    arr = np.where(ink > 0, 0, 255).astype(np.uint8)
    out = BytesIO()
    Image.fromarray(arr, mode="L").save(out, "PNG")
    png = out.getvalue()

    m = measure_heading_bold(png, None)
    assert m.confident
    assert m.is_bold


def test_blank_image_with_zero_bbox_returns_unconfident():
    """Fallback only activates when the lower half actually has text. A
    blank fallback crop must not silently classify as `not bold` with
    confident=True — that would make the LLM fallback path unreachable."""
    img = Image.new("L", (200, 80), color=255)
    out = BytesIO()
    img.save(out, "PNG")
    png = out.getvalue()

    m = measure_heading_bold(png, (0, 0, 0, 0))
    assert not m.confident


def test_single_noise_speck_returns_unconfident():
    """A single tiny dust-speck component must not yield confident=True with a
    garbage ratio. The original SWT contract ('measured, not guessed') breaks
    if a 2-pixel blob can produce is_bold=True at ratio≈1.0. Real heading text,
    even at the lowest fixture resolution, has character heights >> a few px."""
    # 200x80 image with a single 3x3 black speck — looks like sensor noise.
    img = Image.new("L", (200, 80), color=255)
    arr = np.asarray(img).copy()
    arr[40:43, 100:103] = 0  # 3x3 black square — single connected component
    out = BytesIO()
    Image.fromarray(arr, mode="L").save(out, "PNG")
    png = out.getvalue()

    m = measure_heading_bold(png, (0, 0, 0, 0))
    assert not m.confident, (
        f"a 3x3 dust speck must not be confidently classified as a heading; "
        f"got is_bold={m.is_bold} ratio={m.width_height_ratio:.3f} mean_h={m.mean_character_height:.2f}"
    )
