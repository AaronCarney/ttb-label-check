"""Measure what `WIDTH_HEIGHT_RATIO_BOLD_MIN` does to the label corpus.

What it answers: over the labels TTB approved, how bold does the reader measure
the GOVERNMENT WARNING heading, and how many approved labels does the current
cut call *not bold*?

    OCR_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 \\
      nice -n 19 taskset -c 0-5 uv run python -m eval.heading_bold_ratios

`WIDTH_HEIGHT_RATIO_BOLD_MIN` (`app/vision/heading_measure.py`) was, when this
was written, the only corpus-fitted number in the product that could reject a
label outright: a heading measured below it was reported as not bold, and
`common.warning.heading_caps_bold` is a `reject`-severity rule. Its comment said
the value was set on PIL's default bitmap font -- bold blobs at ~0.28, regular
text at ~0.22 -- and that "empirical re-tune against a labeled corpus is still
to come". This is that re-tune's measurement, and what it found is why a
measured weight no longer rejects anything (`docs/decisions.md#0037`). The
script is kept so the measurement can be repeated, against a changed corpus or
a changed reader.

**The ground truth is the approval, not a transcription.** Every label in
`tests/fixtures/labels/manifest.json` carries `registry.status: APPROVED`, and
§16.22(a)(2) requires the heading to appear in bold type. So a real approved
label whose heading the reader measures *confidently* below the cut is a label
this product would reject and TTB did not. That is a one-sided test and it is
the one that matters: it cannot prove the cut is not too low, but it is the only
evidence that says whether it is too high.

The eight `kind: variant` labels are reported apart from the thirty real ones.
Four of them (glare, skew, low light, blur) degrade the image without touching
the printing, so their heading is as bold as the label they derive from: they
are the test of whether a degraded image produces a *confident* wrong answer
rather than the `confident=False` that sends the label to a reviewer. One
(`var-heading-title-case`) repaints the heading, so what it measures is not the
original label's printing and is excluded from the bold population.

Only the warning-carrying face of each label is read -- the heading is on one
face, and the other is a front the measurement never sees.

The run is held to the CPU budget in CLAUDE.local.md -- six threads, and a
two-second pause between images -- because this machine has a thermal fault and
a corpus read is the heaviest thing here. The pause is applied here rather than
left to the caller so that running the documented command is enough.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import deque
from pathlib import Path
from typing import Any

from app.config import Settings
from app.vision.heading_measure import WIDTH_HEIGHT_RATIO_BOLD_MIN
from app.vision.local import LocalVisionExtractor

CORPUS = Path("tests/fixtures/labels")
MANIFEST = CORPUS / "manifest.json"

# The pause between images, in seconds. The owner set this budget on
# 2026-09-17: "it is safe to run the OCR on six threads and with a two second
# pause between each image."
PAUSE_SECONDS = 2.0

# The heading of this variant is repainted, so its stroke width is the
# repainting's and not the approved label's. It is measured and printed like
# the rest, and left out of the population the cut is judged against.
_REPAINTED_HEADING = {"var-heading-title-case"}


def _warning_faces() -> list[dict[str, Any]]:
    """One row per label: which face carries the warning, and what the manifest
    says about the label it came from."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for label in manifest["labels"]:
        which = label.get("warning_image")
        images = label.get("images", {})
        if not which or which not in images:
            continue
        rows.append(
            {
                "id": label["id"],
                "kind": label.get("kind"),
                "face": which,
                "image": images[which],
                "status": (label.get("registry") or {}).get("status"),
            }
        )
    return rows


def _measure(extractor: LocalVisionExtractor, path: Path) -> dict[str, Any]:
    """Run the reader's own `look` and keep the heading measurement it took.

    `look` is used rather than a re-implementation because the measurement is
    taken on the frame the boxes were computed from -- downscaled to
    `MAX_EDGE_PX`, and rotated where the warning is printed up an edge. A
    sweep that opened the image itself would measure a different pixel space
    from the one production measures, and report a real number about it.
    """
    reading = extractor.look(path.read_bytes())
    measurement = reading.heading_measurement
    if measurement is None:
        return {"heading_found": False, "confident": False, "ratio": None, "is_bold": None}
    return {
        "heading_found": True,
        "confident": measurement.confident,
        "ratio": round(measurement.width_height_ratio, 4) if measurement.confident else None,
        "is_bold": measurement.is_bold if measurement.confident else None,
        "stroke_width": round(measurement.mean_stroke_width, 3),
        "char_height": round(measurement.mean_character_height, 3),
    }


def _cut_table(ratios: list[float]) -> list[tuple[float, int]]:
    """How many of these confident measurements each candidate cut calls bold."""
    cuts = [0.10, 0.15, 0.20, 0.22, 0.25, 0.28, 0.30, 0.35, 0.40]
    return [(cut, sum(1 for r in ratios if r > cut)) for cut in cuts]


async def _run(json_out: Path | None) -> int:
    faces = _warning_faces()
    if not faces:
        print(f"no warning faces in {MANIFEST}")
        return 1

    extractor = LocalVisionExtractor(settings=Settings(), ring_buffer=deque(maxlen=8))
    await extractor.ensure_loaded()

    rows: list[dict[str, Any]] = []
    started = time.monotonic()
    for index, face in enumerate(faces):
        if index:
            time.sleep(PAUSE_SECONDS)
        path = CORPUS / face["image"]
        row = {**face, **_measure(extractor, path)}
        rows.append(row)
        ratio = "-" if row["ratio"] is None else f"{row['ratio']:.4f}"
        verdict = "not measured" if not row["confident"] else ("BOLD" if row["is_bold"] else "not")
        print(
            f"{row['id']:<28} {row['kind']:<8} {row['face']:<6} ratio={ratio:>7}  {verdict}",
            flush=True,
        )

    elapsed = time.monotonic() - started

    real = [r for r in rows if r["kind"] == "real"]
    variants = [r for r in rows if r["kind"] != "real"]
    judged = [r for r in real if r["confident"]]
    ratios = sorted(r["ratio"] for r in judged)
    rejected = [r for r in judged if not r["is_bold"]]
    unconfident = [r for r in real if not r["confident"]]

    print(f"\n{len(rows)} warning faces read in {elapsed:.1f}s")
    print(f"current cut: WIDTH_HEIGHT_RATIO_BOLD_MIN = {WIDTH_HEIGHT_RATIO_BOLD_MIN}")
    print(
        f"\n{len(real)} real approved labels: {len(judged)} measured confidently, "
        f"{len(unconfident)} not measured (those go to a reviewer, not a rejection)"
    )
    if ratios:
        print(
            f"  confident ratios: min {ratios[0]:.4f}  "
            f"median {statistics.median(ratios):.4f}  max {ratios[-1]:.4f}"
        )
        print(f"  full sorted list: {', '.join(f'{r:.3f}' for r in ratios)}")
        print(
            f"\n  *** at {WIDTH_HEIGHT_RATIO_BOLD_MIN}, {len(rejected)} of {len(judged)} "
            f"confidently-measured approved labels are called NOT BOLD "
            f"and would be rejected ***"
        )
        for row in sorted(rejected, key=lambda r: r["ratio"]):
            print(f"      {row['id']:<28} ratio={row['ratio']:.4f}")
        print("\n  how many of the confident approved labels each cut calls bold:")
        for cut, kept in _cut_table(ratios):
            mark = "  <- current" if cut == WIDTH_HEIGHT_RATIO_BOLD_MIN else ""
            print(f"      cut {cut:<5} -> {kept:>2}/{len(judged)} bold{mark}")

    if variants:
        print(f"\n{len(variants)} variants, reported apart:")
        for row in variants:
            note = (
                "  (heading repainted, excluded above)" if row["id"] in _REPAINTED_HEADING else ""
            )
            ratio = "-" if row["ratio"] is None else f"{row['ratio']:.4f}"
            verdict = (
                "not measured"
                if not row["confident"]
                else ("BOLD" if row["is_bold"] else "NOT BOLD")
            )
            print(f"    {row['id']:<28} ratio={ratio:>7}  {verdict}{note}")

    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(f"\nper-label rows written to {json_out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="write per-label rows here")
    args = parser.parse_args()
    return asyncio.run(_run(args.json))


if __name__ == "__main__":
    raise SystemExit(main())
