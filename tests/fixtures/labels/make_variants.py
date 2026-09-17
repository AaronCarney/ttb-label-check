"""Build the flawed label variants listed in manifest.json.

Each manifest entry with a "variant" block names the real label it derives from and the change.
Image changes are written to variants/<id>.<ext>; changes that touch only the application data
(ABV mismatch, brand differing in case or punctuation) reuse the source image unchanged.

Run from this folder:
    uv run --with pillow python make_variants.py

Output is deterministic: fixed seeds, fixed parameters, no dependence on wall-clock time.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise FileNotFoundError(f"no TrueType font found among {candidates}")


def glare(img: Image.Image, cx: float, cy: float, radius: float, strength: float) -> Image.Image:
    """Add a soft white hotspot centred at (cx, cy), given as fractions of width and height."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    r = int(radius * max(w, h))
    x, y = int(cx * w), int(cy * h)
    ImageDraw.Draw(mask).ellipse([x - r, y - r, x + r, y + r], fill=int(255 * strength))
    mask = mask.filter(ImageFilter.GaussianBlur(r / 2.5))
    white = Image.new("RGB", (w, h), (255, 255, 255))
    return Image.composite(white, img, mask)


def skew(img: Image.Image, angle: float, shear: float) -> Image.Image:
    """Rotate by angle degrees and apply a horizontal shear, as from a hand-held photo."""
    out = img.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=(60, 60, 60))
    w2, h2 = out.size
    return out.transform(
        (w2 + int(abs(shear) * h2), h2),
        Image.AFFINE,
        (1, shear, -abs(shear) * h2 if shear > 0 else 0, 0, 1, 0),
        resample=Image.BICUBIC,
        fillcolor=(60, 60, 60),
    )


def low_light(img: Image.Image, brightness: float, noise: int, seed: int) -> Image.Image:
    """Darken, lower contrast and add sensor-like noise."""
    out = ImageEnhance.Brightness(img).enhance(brightness)
    out = ImageEnhance.Contrast(out).enhance(0.8)
    rng = random.Random(seed)
    noise_img = Image.effect_noise(out.size, noise).convert("RGB")
    rng.random()  # the seed documents intent; effect_noise is itself deterministic per size
    return Image.blend(out, noise_img, 0.08)


def blur(img: Image.Image, radius: float) -> Image.Image:
    return img.filter(ImageFilter.GaussianBlur(radius))


def _wrap(
    draw: ImageDraw.ImageDraw,
    words: list[tuple[str, bool]],
    fonts: dict[bool, ImageFont.FreeTypeFont],
    width: int,
) -> list[list[tuple[str, bool]]]:
    lines: list[list[tuple[str, bool]]] = [[]]
    used = 0
    space = draw.textlength(" ", font=fonts[False])
    for word, bold in words:
        wl = draw.textlength(word, font=fonts[bold])
        if lines[-1] and used + space + wl > width:
            lines.append([])
            used = 0
        used += (space if lines[-1] else 0) + wl
        lines[-1].append((word, bold))
    return lines


def replace_warning(img: Image.Image, box: list[int], heading: str, body: str) -> Image.Image:
    """Paint over the warning block inside box [x0, y0, x1, y1] and set new text in its place.

    The heading is set bold and the body regular, as 27 CFR 16.22(a)(2) prescribes, so the only
    difference from the source is the wording the variant names. The fill colour is the median of
    the box's border pixels, so the patch matches the label stock.
    """
    out = img.copy()
    x0, y0, x1, y1 = box
    border = [out.getpixel((x, y0)) for x in range(x0, x1)] + [
        out.getpixel((x, y1 - 1)) for x in range(x0, x1)
    ]
    border.sort(key=sum)
    bg = border[len(border) // 2]
    ink = (0, 0, 0) if sum(bg[:3]) > 384 else (255, 255, 255)
    draw = ImageDraw.Draw(out)
    draw.rectangle(box, fill=bg)
    words = [(w, True) for w in heading.split()] + [(w, False) for w in body.split()]
    width, height = x1 - x0 - 4, y1 - y0 - 4
    size = 160  # start large and shrink until the block fits, so the text fills the box like the source
    while size > 6:
        fonts = {False: _font(FONT_CANDIDATES, size), True: _font(FONT_BOLD_CANDIDATES, size)}
        lines = _wrap(draw, words, fonts, width)
        line_h = int(size * 1.2)
        if line_h * len(lines) <= height:
            break
        size -= 1
    y = y0 + 2
    for line in lines:
        x = x0 + 2
        for word, bold in line:
            draw.text((x, y), word, font=fonts[bold], fill=ink)
            x += draw.textlength(word + " ", font=fonts[bold])
        y += line_h
    return out


def build(entry: dict, labels: dict[str, dict]) -> dict[str, str]:
    v = entry["variant"]
    src = labels[v["derives_from"]]
    kind, p = v["kind"], v.get("params", {})
    images = dict(src["images"])
    target = p.get("image", "back" if kind.startswith("warning") else "front")
    if kind in {"abv_mismatch", "brand_case_punctuation"}:
        return images
    img = Image.open(HERE / src["images"][target]).convert("RGB")
    if kind == "glare":
        img = glare(img, p["cx"], p["cy"], p["radius"], p["strength"])
    elif kind == "skew":
        img = skew(img, p["angle"], p["shear"])
    elif kind == "low_light":
        img = low_light(img, p["brightness"], p["noise"], p["seed"])
    elif kind == "blur":
        img = blur(img, p["radius"])
    elif kind in {"warning_heading_title_case", "warning_wording_altered"}:
        img = replace_warning(img, p["box"], p["heading"], p["body"])
    else:
        raise ValueError(f"unknown variant kind {kind!r}")
    rel = f"variants/{entry['id']}-{target}.jpg"
    (HERE / "variants").mkdir(exist_ok=True)
    img.save(HERE / rel, quality=90)
    images[target] = rel
    return images


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    labels = {e["id"]: e for e in manifest["labels"]}
    for entry in manifest["labels"]:
        if "variant" not in entry:
            continue
        built = build(entry, labels)
        if built != entry["images"]:
            raise SystemExit(f"{entry['id']}: manifest images {entry['images']} != built {built}")
        print(f"{entry['id']}: {entry['variant']['kind']} -> {built}")


if __name__ == "__main__":
    main()
