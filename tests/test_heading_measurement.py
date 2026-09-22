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


def test_tiny_crop_returns_unconfident():
    """A crop smaller than 8x8 pixels can't host enough components."""
    png = _png_text("GOVERNMENT WARNING", size=24, weight="bold")
    m = measure_heading_bold(png, (0, 0, 4, 4))
    assert not m.confident


def _lower_half_bold_text_png() -> bytes:
    """A 200x80 label whose top half is blank and whose lower half carries bold
    text — the shape that made the deleted lower-half fallback look plausible."""
    import cv2

    img = Image.new("L", (200, 80), color=255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(24)
    except TypeError:
        font = ImageFont.load_default()
    draw.text((10, 50), "GOVERNMENT WARNING", fill=0, font=font)
    arr = np.asarray(img)
    ink = (arr < 128).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    ink = cv2.dilate(ink, kernel, iterations=2)
    arr = np.where(ink > 0, 0, 255).astype(np.uint8)
    out = BytesIO()
    Image.fromarray(arr, mode="L").save(out, "PNG")
    return out.getvalue()


def test_zero_bbox_does_not_measure_the_lower_half():
    """A degenerate bbox means no heading region, so no measurement.

    The earlier version cropped the lower half of the whole image and reported
    `confident=True` on whatever ink it found there. That crop is body copy and
    the mandated statement, not the heading, so the ratio is a real number
    about the wrong pixels and the caller cannot tell. Text being present in
    the lower half is exactly what made it look right, so this is the case
    that has to report unconfident.
    """
    m = measure_heading_bold(_lower_half_bold_text_png(), (0, 0, 0, 0))
    assert not m.confident
    assert not m.is_bold  # zeroed: "not measured", never "measured as not bold"
    assert m.width_height_ratio == 0.0


def test_none_bbox_does_not_measure_the_lower_half():
    """Same for a missing bbox: the layout call returning nothing for the
    heading is the reader's failure, not evidence about the label."""
    m = measure_heading_bold(_lower_half_bold_text_png(), None)
    assert not m.confident
    assert m.mean_character_height == 0.0


def test_blank_crop_returns_unconfident():
    """A real heading bbox over blank paper holds no ink to measure. Blank
    must not classify as `not bold` with confident=True: there is a difference
    between a heading measured as light and no heading found at all."""
    img = Image.new("L", (200, 80), color=255)
    out = BytesIO()
    img.save(out, "PNG")

    m = measure_heading_bold(out.getvalue(), (10, 10, 190, 70))
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

    m = measure_heading_bold(png, (90, 30, 120, 60))
    assert not m.confident, (
        f"a 3x3 dust speck must not be confidently classified as a heading; "
        f"got is_bold={m.is_bold} ratio={m.width_height_ratio:.3f} "
        f"mean_h={m.mean_character_height:.2f}"
    )


def test_light_text_on_a_dark_ground_measures_the_letters_not_the_gaps():
    """A label printing its warning white on black is measured the same as
    black on white.

    The threshold took the dark side of the crop as ink. On a light-on-dark
    label that is the ground, and the measurement reported the width of the
    spaces between the letters as their stroke width.
    """
    png = _png_text("GOVERNMENT WARNING", size=24, weight="bold")
    inverted = BytesIO()
    Image.eval(Image.open(BytesIO(png)), lambda v: 255 - v).save(inverted, "PNG")
    bbox = (0, 0, 260, 80)

    dark_on_light = measure_heading_bold(png, bbox)
    light_on_dark = measure_heading_bold(inverted.getvalue(), bbox)

    assert light_on_dark.confident
    assert light_on_dark.mean_stroke_width == dark_on_light.mean_stroke_width
    assert light_on_dark.mean_character_height == dark_on_light.mean_character_height
