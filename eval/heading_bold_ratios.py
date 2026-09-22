"""Measure the warning heading's weight against its body, on real and rendered labels.

What it answers: does `RELATIVE_WEIGHT_BOLD_MIN` (`app/vision/heading_measure.py`)
separate a bold heading from a regular one, on labels TTB approved and on
warnings rendered with a known weight, and does a worse photograph ever move a
heading to the wrong side of it?

    nice -n 19 taskset -c 0-3 uv run python -m eval.heading_bold_ratios
    nice -n 19 taskset -c 0-3 uv run python -m eval.heading_bold_ratios --synthetic

No OCR runs. The boxes come from frozen readings (`tests/recordings/reader/`,
and `eval/data/registry-readings/` where it has been fetched), and each
measurement is taken again from the image through the reader's own
`remeasure_heading`, so the crop is the frame production measures.

**Real labels.** Every label here is TTB-approved, and §16.22(a)(2) requires
its heading in bold, so a real label is never evidence of a regular heading.
It is evidence of how often the measurement can say "bold" at all, and of
what a worse photograph does: each warning face is measured again after a
Gaussian blur of 1, 2 and 3 pixels and after JPEG compression at quality 20,
from the same boxes.

**Rendered warnings** (`--synthetic`) are the only place the weight is known
both ways. The statement is set in the DejaVu faces opencv-python ships, with
the heading bold over a regular body, regular over regular, and all of it
bold, across type sizes, blur, light-on-dark, lower case, JPEG quality 20 and
half resolution. The cut and the letter-height floor are set on these.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.vision import heading_measure
from app.vision.heading_measure import (
    LETTER_HEIGHT_MIN_PX,
    RELATIVE_WEIGHT_BOLD_MIN,
    SHARPNESS_MAX,
    HeadingMeasurement,
    measure_heading_bold_image,
)
from app.vision.local import (
    _Box,
    _find_heading,
    _frame,
    _measure_heading,
    _warning_block,
    remeasure_heading,
    thaw_reading,
)
from eval.corpus_check import LABELS_ROOT, RECORDINGS_ROOT, REGISTRY_READINGS

FONTS = Path(cv2.__file__).parent / "qt" / "fonts"
FACES = {
    "dejavu": ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
    "dejavu-condensed": ("DejaVuSansCondensed.ttf", "DejaVuSansCondensed-Bold.ttf"),
}
SIZES = (10, 12, 14, 16, 20, 26, 34)
BLURS = (0.0, 1.0, 2.0, 3.0)
DEGRADES = ("none", "jpeg20", "half", "half+jpeg20")
KINDS = {"bold-heading": (True, False), "regular-heading": (False, False), "all-bold": (True, True)}

HEADING = "GOVERNMENT WARNING:"
FIRST = " (1) ACCORDING TO THE SURGEON GENERAL,"
BODY = (
    "WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES DURING",
    "PREGNANCY BECAUSE OF THE RISK OF BIRTH DEFECTS.",
    "(2) CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR",
    "ABILITY TO DRIVE A CAR OR OPERATE MACHINERY, AND",
)


@dataclass(frozen=True)
class RenderedWarning:
    """One rendered warning: how it was set, and what it went through."""

    face: str = "dejavu"
    size: int = 20
    kind: str = "bold-heading"
    lower: bool = False
    blur: float = 0.0
    invert: bool = False
    degrade: str = "none"


def render(w: RenderedWarning) -> tuple[Image.Image, list[_Box]]:
    """The warning as a frame, and the boxes an OCR engine would return for it.

    Each line is one box drawn tight around its ink, and the heading shares
    its box with the start of the statement, as the engine usually returns it.
    """
    regular, bold = (ImageFont.truetype(str(FONTS / name), w.size) for name in FACES[w.face])
    heading_bold, body_bold = KINDS[w.kind]
    heading_font = bold if heading_bold else regular
    body_font = bold if body_bold else regular
    first = FIRST.lower() if w.lower else FIRST
    body = [line.capitalize() for line in BODY] if w.lower else list(BODY)

    step = int(w.size * 1.35)
    image = Image.new("L", (w.size * 40, step * (len(body) + 2)), 255)
    draw = ImageDraw.Draw(image)
    x, y = w.size, w.size // 2
    draw.text((x, y), HEADING, font=heading_font, fill=0)
    after = x + draw.textlength(HEADING, font=heading_font)
    draw.text((after, y), first, font=body_font, fill=0)
    h0, h1 = (
        draw.textbbox((x, y), HEADING, font=heading_font),
        draw.textbbox((after, y), first, font=body_font),
    )
    boxes = [(min(h0[0], h1[0]), min(h0[1], h1[1]), max(h0[2], h1[2]), max(h0[3], h1[3]))]
    texts = [HEADING + first]
    for i, line in enumerate(body, start=1):
        draw.text((x, y + step * i), line, font=body_font, fill=0)
        boxes.append(draw.textbbox((x, y + step * i), line, font=body_font))
        texts.append(line)

    if w.blur:
        image = image.filter(ImageFilter.GaussianBlur(w.blur))
    if w.invert:
        image = Image.eval(image, lambda v: 255 - v)
    scale = 1.0
    if "half" in w.degrade:
        scale = 0.5
        image = image.resize((image.width // 2, image.height // 2), Image.Resampling.BILINEAR)
    if "jpeg20" in w.degrade:
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=20)
        image = Image.open(BytesIO(buffer.getvalue()))
    frame = image.convert("RGB")
    return frame, [
        _Box(b[0] * scale, b[1] * scale, b[2] * scale, b[3] * scale, text=t, score=0.95)
        for b, t in zip(boxes, texts, strict=True)
    ]


def measure(w: RenderedWarning) -> HeadingMeasurement:
    """The production measurement of one rendered warning."""
    frame, boxes = render(w)
    measurement = _measure_heading(frame, boxes)
    if measurement is None:
        raise AssertionError(f"the reader found no heading in {w}")
    return measurement


def warnings(
    faces: tuple[str, ...] = tuple(FACES),
    sizes: tuple[int, ...] = SIZES,
    kinds: tuple[str, ...] = tuple(KINDS),
    blurs: tuple[float, ...] = BLURS,
    degrades: tuple[str, ...] = DEGRADES,
) -> Iterator[RenderedWarning]:
    for face in faces:
        for size in sizes:
            for kind in kinds:
                for lower in (False, True):
                    for blur in blurs:
                        for invert in (False, True):
                            for degrade in degrades:
                                yield RenderedWarning(
                                    face, size, kind, lower, blur, invert, degrade
                                )


def _span(values: list[float]) -> str:
    return f"{min(values):.3f} to {max(values):.3f}" if values else "none"


def report_synthetic() -> None:
    rows = [(w, measure(w)) for w in warnings()]
    print(f"{len(rows)} rendered warnings, cut {RELATIVE_WEIGHT_BOLD_MIN}\n")
    for kind in KINDS:
        of_kind = [(w, m) for w, m in rows if w.kind == kind]
        measured = [(w, m) for w, m in of_kind if m.confident]
        reasons = Counter(m.unmeasured_reason for _w, m in of_kind if not m.confident)
        bold = sum(m.is_bold for _w, m in measured)
        weights = _span([m.relative_weight for _w, m in measured])
        print(
            f"{kind:<16} {len(of_kind)} rendered, {len(measured)} measured, "
            f"{bold} called bold; relative weight {weights}"
        )
        print(f"{'':<16} not measured: {dict(reasons)}")
        for degrade in DEGRADES:
            sub = [m.relative_weight for w, m in measured if w.degrade == degrade]
            print(f"{'':<16}   {degrade:<12} {_span(sub)}")
    # The floors' own evidence: the same warnings with the letter-height floor
    # switched off, so each floor's effect shows on its own.
    heading_measure.LETTER_HEIGHT_MIN_PX = 0.0
    try:
        open_rows = [(w, measure(w)) for w in warnings(kinds=("bold-heading", "regular-heading"))]
    finally:
        heading_measure.LETTER_HEIGHT_MIN_PX = LETTER_HEIGHT_MIN_PX
    print("\nwith no letter-height floor, headings that pass the sharpness floor:")
    for low, high in (
        (0.0, 8.0),
        (8.0, 10.0),
        (10.0, LETTER_HEIGHT_MIN_PX),
        (LETTER_HEIGHT_MIN_PX, 1e9),
    ):
        spans = {
            kind: _span(
                [
                    m.relative_weight
                    for w, m in open_rows
                    if w.kind == kind and m.confident and low <= m.letter_height < high
                ]
            )
            for kind in ("bold-heading", "regular-heading")
        }
        print(
            f"  letters {low:>4.0f} to {min(high, 999):>3.0f} px: bold {spans['bold-heading']}; "
            f"regular {spans['regular-heading']}"
        )
    print("\nwith no sharpness floor, letters at or above the height floor:")
    heading_measure.SHARPNESS_MAX = float("inf")
    try:
        for kind in ("bold-heading", "regular-heading"):
            blurred = [
                (w.blur, measure(w))
                for w in warnings(kinds=(kind,), blurs=(2.0, 3.0), degrades=("none",))
            ]
            for blur in (2.0, 3.0):
                ratios = [m.relative_weight for b, m in blurred if b == blur and m.confident]
                print(f"  {kind:<16} blur {blur}: {_span(ratios)}")
    finally:
        heading_measure.SHARPNESS_MAX = SHARPNESS_MAX


def _frozen() -> Iterator[tuple[str, Path, dict]]:
    """Every frozen warning face: which set it is from, its file, its data."""
    for group, root in (("corpus", RECORDINGS_ROOT), ("held-out", REGISTRY_READINGS)):
        for path in sorted(root.rglob("*.json")):
            data = json.loads(path.read_text())
            if data.get("heading_measurement") is not None:
                yield group, path, data


def _image(data: dict) -> Path:
    named = Path(data["image"])
    return named if named.exists() else LABELS_ROOT / named


def _degraded(image_bytes: bytes, how: str) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    if how.startswith("blur"):
        image = image.filter(ImageFilter.GaussianBlur(float(how[4:])))
    buffer = BytesIO()
    if how == "jpeg20":
        image.save(buffer, format="JPEG", quality=20)
    else:
        image.save(buffer, format="PNG")
    return buffer.getvalue()


def report_real() -> None:
    faces = list(_frozen())
    for group in ("corpus", "held-out"):
        rows = [(p, d) for g, p, d in faces if g == group]
        if not rows:
            print(f"{group}: no frozen readings")
            continue
        found = [d["heading_measurement"] for _p, d in rows]
        measured = [m for m in found if m["confident"]]
        bold = [m for m in measured if m["is_bold"]]
        reasons = Counter(m["unmeasured_reason"] for m in found if not m["confident"])
        print(
            f"{group}: {len(found)} warning faces with a heading; {len(measured)} measured, "
            f"{len(bold)} called bold"
        )
        print(f"  not measured: {dict(reasons)}")
        if measured:
            weights = sorted(m["relative_weight"] for m in measured)
            below = [f"{w:.3f}" for w in weights if w < RELATIVE_WEIGHT_BOLD_MIN]
            print(
                f"  relative weight {_span(weights)}, median {statistics.median(weights):.3f}; "
                f"not bold: {', '.join(below)}"
            )

    # The only regular-against-regular evidence a real photograph gives: each
    # body line of the warning measured as if it were the heading, against the
    # statement's other lines.
    lines: list[float] = []
    for _group, _path, data in faces:
        reading = thaw_reading(data)
        block = _warning_block(reading.warning_boxes)
        heading = _find_heading(reading.warning_boxes)
        if block is None or heading is None:
            continue
        body = [b for b in block[3] if all(b is not h for h in heading[1])]
        if len(body) < 3:
            continue
        frame = _frame(_image(data).read_bytes())
        if reading.rotation:
            frame = frame.rotate(reading.rotation, expand=True)
        for line in body:
            others = [b.as_bbox() for b in body if b is not line]
            m = measure_heading_bold_image(frame, line.as_bbox(), others)
            if m.confident:
                lines.append(m.relative_weight)
    print(
        f"\none body line against the others, both sets: {len(lines)} measured, "
        f"{_span(lines)}, {sum(w >= RELATIVE_WEIGHT_BOLD_MIN for w in lines)} at or above the cut"
    )

    print("\ncorpus warning faces measured again from worse copies of the same image:")
    for how in ("blur1", "blur2", "blur3", "jpeg20"):
        moved: Counter[str] = Counter()
        for group, path, data in faces:
            if group != "corpus":
                continue
            before = data["heading_measurement"]
            degraded = _degraded(_image(data).read_bytes(), how)
            after = remeasure_heading(degraded, thaw_reading(data)).heading_measurement
            assert after is not None
            key = (
                "bold" if before["is_bold"] else "not bold" if before["confident"] else "unmeasured"
            )
            new = "bold" if after.is_bold else "not bold" if after.confident else "unmeasured"
            moved[f"{key} -> {new}"] += 1
            if key != new:
                print(
                    f"    {how}: {path}: {key} ({before['relative_weight']:.3f}) -> {new} "
                    f"({after.relative_weight:.3f}, {after.unmeasured_reason})"
                )
        print(f"  {how:<7} {dict(sorted(moved.items()))}")
    print(f"\ncut {RELATIVE_WEIGHT_BOLD_MIN}, letters at least {LETTER_HEIGHT_MIN_PX} px")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", help="rendered warnings only")
    args = parser.parse_args()
    if args.synthetic:
        report_synthetic()
    else:
        report_real()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
