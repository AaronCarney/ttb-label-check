"""Measure the box shapes the sideways-text gate in `app.vision.local` turns on.

What it answers: over the label corpus, how tall-and-thin do the detector's
boxes get, and does that separate the labels whose warning reads upright from
the one whose warning is printed up the edge?

    uv run python -m eval.box_ratios

`_has_sideways_text` decides whether to pay for a rotated re-read, and it
decides on shape alone: a box's height over its width. `_SIDEWAYS_RATIO`,
`_SIDEWAYS_MIN_BOXES` and `_SIDEWAYS_LONE_RATIO` are the thresholds, and the
comment above them is the only record of what they were set from. That comment
named a corpus of 72 images. There are 62, so the measurement it cites cannot
be the one that was made, and the thresholds have carried an unverifiable
justification since. This re-derives it from the images that actually exist.

Every image in the corpus is read, not just the faces carrying a warning: the
gate runs on every frame the reader is handed, so a front label that produces a
tall box costs a re-read exactly as a back one does.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import deque
from pathlib import Path
from typing import Any

from PIL import Image

from app.config import Settings
from app.vision.local import (
    _SIDEWAYS_LONE_RATIO,
    _SIDEWAYS_MIN_BOXES,
    _SIDEWAYS_RATIO,
    LocalVisionExtractor,
    _find_heading,
    _has_sideways_text,
)

CORPUS = Path("tests/fixtures/labels")
MANIFEST = CORPUS / "manifest.json"


def _warning_faces() -> set[str]:
    """The corpus-relative path of every face the manifest says carries the
    government warning. The rest are fronts and other backs."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    faces: set[str] = set()
    for label in manifest["labels"]:
        which = label.get("warning_image")
        if which and which in label.get("images", {}):
            faces.add(label["images"][which])
    return faces


def _measure(extractor: LocalVisionExtractor, path: Path) -> dict[str, Any]:
    with Image.open(path) as handle:
        image = handle.convert("RGB")
    boxes = extractor._boxes(image)
    ratios = [(b.y1 - b.y0) / max(1e-6, b.x1 - b.x0) for b in boxes]
    return {
        "image": str(path.relative_to(CORPUS)),
        "boxes": len(boxes),
        "tallest_ratio": round(max(ratios), 2) if ratios else 0.0,
        "over_sideways_ratio": sum(1 for r in ratios if r >= _SIDEWAYS_RATIO),
        "over_lone_ratio": sum(1 for r in ratios if r >= _SIDEWAYS_LONE_RATIO),
        "gate_fires": _has_sideways_text(boxes),
        # The gate is consulted only where the upright pass found no warning
        # heading (local.py, `if found is None and _has_sideways_text(boxes)`).
        # An image whose heading was found never reaches it, however tall its
        # boxes are, so the thresholds answer for that population and no other.
        "heading_found_upright": _find_heading(boxes) is not None,
    }


async def _run(json_out: Path | None) -> int:
    images = sorted(CORPUS.glob("*/*.jpg"))
    if not images:
        print(f"no images under {CORPUS}")
        return 1
    warning_faces = _warning_faces()

    extractor = LocalVisionExtractor(settings=Settings(), ring_buffer=deque(maxlen=8))
    await extractor.ensure_loaded()

    rows: list[dict[str, Any]] = []
    started = time.monotonic()
    for path in images:
        row = _measure(extractor, path)
        row["carries_warning"] = row["image"] in warning_faces
        rows.append(row)
        print(
            f"{row['image']:<46} boxes={row['boxes']:>4} "
            f"tallest={row['tallest_ratio']:>6} "
            f">={_SIDEWAYS_RATIO}: {row['over_sideways_ratio']:>3} "
            f"gate={'fires' if row['gate_fires'] else '-':>5}",
            flush=True,
        )

    elapsed = time.monotonic() - started
    tallest = max(rows, key=lambda r: r["tallest_ratio"])
    # The population the thresholds actually govern.
    asked = [r for r in rows if not r["heading_found_upright"]]
    fires = [r for r in asked if r["gate_fires"]]
    quiet = [r for r in asked if not r["gate_fires"]]

    print(
        f"\n{len(rows)} images read in {elapsed:.1f}s "
        f"(thresholds: ratio {_SIDEWAYS_RATIO}, min boxes {_SIDEWAYS_MIN_BOXES}, "
        f"lone {_SIDEWAYS_LONE_RATIO})"
    )
    print(f"  tallest box over the whole corpus: {tallest['tallest_ratio']} on {tallest['image']}")
    print(
        f"  {len(rows) - len(asked)} images found their warning heading upright "
        f"and never reach the gate"
    )
    print(
        f"  of the {len(asked)} that do reach it: {len(fires)} pay for the rotated "
        f"re-read, {len(quiet)} are spared it"
    )
    if quiet:
        print(f"    tallest box among the spared: {max(r['tallest_ratio'] for r in quiet)}")
    print("  images that pay for the re-read:")
    for row in sorted(fires, key=lambda r: -r["tallest_ratio"]):
        print(
            f"    {row['image']:<46} tallest={row['tallest_ratio']:>6} "
            f">={_SIDEWAYS_RATIO}: {row['over_sideways_ratio']:>3} "
            f"{'(warning face)' if row['carries_warning'] else ''}"
        )
    others = [r for r in rows if r["heading_found_upright"] and r["gate_fires"]]
    if others:
        print(
            f"  {len(others)} images have gate-shaped boxes but found their heading "
            f"upright, so the gate is never asked:"
        )
        for row in sorted(others, key=lambda r: -r["tallest_ratio"]):
            print(f"    {row['image']:<46} tallest={row['tallest_ratio']:>6}")

    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(f"\nper-image rows written to {json_out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="write per-image rows here")
    args = parser.parse_args()
    return asyncio.run(_run(args.json))


if __name__ == "__main__":
    raise SystemExit(main())
