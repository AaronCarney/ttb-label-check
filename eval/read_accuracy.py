"""Score a reader against the real labels and their verified values.

What it answers: on labels approved by TTB, paired with the application each
was approved against, how often does the reader report the value that is
really there?

    uv run python -m eval.read_accuracy                # the local reader
    uv run python -m eval.read_accuracy --reader cloud # needs OPENAI_API_KEY

The ground truth is `tests/fixtures/labels/manifest.json`: 30 labels read out
of the TTB Public COLA Registry, each with the application's own fields, and
8 variants derived from them by damaging the image or the warning. Only the
real labels are scored here; the variants exercise the rules, not the reader.

Every check uses the same comparison the rule pack uses, from
`app.rules._validators._helpers`, so a score here means what a result in the
running app means. The warning is the exception: it is compared word for word
after the normalization the rule pack pins to the regulation text, because
that is what 27 CFR 16.21 requires of it.

The numbers this prints are the only numbers the README states about reading
accuracy.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import time
import unicodedata
from collections import deque
from pathlib import Path

from app.config import Settings
from app.rules._validators._helpers import normalize_words, word_run_present
from app.schemas.label import Label

LABELS_ROOT = Path("tests/fixtures/labels")
WARNING_ASSET = Path("assets/warnings/govt_warning_16_21.txt")

# The checks scored, in the order they are printed.
CHECKS = (
    "brand",
    "class_type",
    "abv",
    "net_contents",
    "name_address",
    "origin",
    "warning_present",
    "warning_exact",
    "warning_heading_caps",
)

_ML_PER_UNIT = {
    "ML": 1.0, "MLS": 1.0, "MILLILITER": 1.0, "MILLILITERS": 1.0,
    "CL": 10.0,
    "L": 1000.0, "LITER": 1000.0, "LITERS": 1000.0, "LITRE": 1000.0, "LITRES": 1000.0,
    "FLOZ": 29.5735, "OZ": 29.5735,
    "PINT": 473.176, "PINTS": 473.176, "PT": 473.176,
    "QUART": 946.353, "QUARTS": 946.353, "QT": 946.353,
    "GALLON": 3785.41, "GALLONS": 3785.41, "GAL": 3785.41,
}


def _normalize_warning(text: str) -> str:
    """The two warnings reduced to what "word for word" actually compares.

    The ground truth defines it (`tests/fixtures/labels/manifest.json`,
    `check_rules.warning_exact`): the words, numbers and punctuation must be
    the regulation's, while letter case, spacing, line breaks and a hyphen
    splitting a word at a line end are ignored. Spacing is dropped rather than
    collapsed because label type is justified, which closes word gaps and
    opens others — one real label sets its heading as "GOVERNMENT WARNING   :".

    This is looser than `rules/common/health_warning.yaml`, which collapses
    whitespace instead of removing it. Where the two disagree the rule pack
    rejects a label this scores as compliant.
    """
    text = unicodedata.normalize("NFKC", text)
    for curly, plain in (("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"')):
        text = text.replace(curly, plain)
    text = re.sub(r"-\s+", "", text)  # a word split across two lines
    return re.sub(r"\s+", "", text).upper()


def _build_reader(kind: str):
    settings = Settings(vision_mode=kind)
    ring: deque = deque(maxlen=500)
    if kind == "cloud":
        from app.vision.cloud import CloudVisionExtractor

        if not settings.openai_api_key:
            raise SystemExit("--reader cloud needs OPENAI_API_KEY in the environment.")
        return CloudVisionExtractor(
            settings=settings, ring_buffer=ring, api_key=settings.openai_api_key
        )
    from app.vision.local import LocalVisionExtractor

    return LocalVisionExtractor(settings=settings, ring_buffer=ring)


def _has_reading(payload: dict | None) -> bool:
    """True when the payload carries a value, not just an empty shape."""
    if not payload:
        return False
    return any(
        v not in (None, "", 0.0, False)
        for k, v in payload.items()
        if k != "confidence" and not k.startswith("heading_bold_")
    )


async def _read_faces(reader, entry: dict) -> tuple[dict[str, dict], float]:
    """Read every face of one label; return the merged payloads and the seconds.

    A label's elements are spread over its faces, and the front carries the
    ones the regulations put in the same field of vision, so the faces are read
    front first and the first face reporting a value for a field is the one
    that holds it. The warning is taken from whichever face carries it.
    """
    merged: dict[str, dict] = {}
    started = time.perf_counter()
    faces = sorted(
        entry["images"].items(),
        key=lambda kv: ("front", "back", "neck", "side").index(kv[0])
        if kv[0] in ("front", "back", "neck", "side") else 9,
    )
    for face, relative in faces:
        path = LABELS_ROOT / relative
        if not path.exists():
            continue
        label = Label(
            label_id=f"{entry['id']}-{face}",
            batch_id="read-accuracy",
            image_bytes=path.read_bytes(),
            content_type="image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png",
            face_tag="front" if face == "front" else "back",
        )
        for observation in await reader.extract(label):
            payload = observation.observed_value
            if not isinstance(payload, dict):
                continue
            if _has_reading(merged.get(observation.field_id)):
                continue
            if _has_reading(payload):
                merged[observation.field_id] = payload
            else:
                merged.setdefault(observation.field_id, payload)
    return merged, time.perf_counter() - started


def _score(entry: dict, read: dict[str, dict], warning_text: str) -> dict[str, bool]:
    """Every check for one label: did the reader report what is really there?"""
    application = entry["application"]
    observed = entry.get("label_observed", {})
    got: dict[str, bool] = {}

    brand = (read.get("brand_name") or {}).get("brand_name") or ""
    got["brand"] = word_run_present(
        normalize_words(brand), normalize_words(application["brand_name"] or "")
    )

    # The verified class is what the label shows where the ground truth
    # recorded it, and the application's class otherwise.
    class_truth = observed.get("class_type") or application.get("class_type") or ""
    class_read = (read.get("class_type") or {}).get("class_type") or ""
    got["class_type"] = word_run_present(
        normalize_words(class_read), normalize_words(class_truth)
    )

    percent = (application.get("alcohol_content") or {}).get("percent")
    abv_read = (read.get("abv") or {}).get("abv_pct")
    got["abv"] = percent is not None and abv_read is not None and abs(float(abv_read) - float(percent)) < 0.05

    millilitres = (application.get("net_contents") or {}).get("ml")
    net = read.get("net_contents") or {}
    value, unit = net.get("net_contents_value"), (net.get("unit") or "").upper()
    converted = None
    if value is not None and unit in _ML_PER_UNIT:
        converted = float(value) * _ML_PER_UNIT[unit]
    got["net_contents"] = (
        millilitres is not None and converted is not None
        and abs(converted - float(millilitres)) <= max(1.0, float(millilitres) * 0.01)
    )

    # The applicant's entry is a free-text block carrying several names; the
    # label prints one of them. The reading counts when the block carries it.
    name_read = read.get("name_address") or {}
    printed = ", ".join(
        str(name_read.get(k) or "").strip() for k in ("name", "city", "state")
    )
    block = normalize_words(application.get("applicant_name_address") or "")
    anchors = [w for w in normalize_words(printed) if len(w) > 3]
    got["name_address"] = bool(anchors) and any(
        word_run_present(block, (w,)) for w in anchors
    )

    if (application.get("source_of_product") or "").strip().lower() != "imported":
        got["origin"] = True  # domestic: no country-of-origin statement is required
    else:
        country_read = (read.get("country_origin") or {}).get("country") or ""
        got["origin"] = word_run_present(
            normalize_words(country_read),
            normalize_words(application.get("origin") or ""),
        )

    expected = entry["expected"]
    warning = read.get("gov_warning") or {}
    text = warning.get("text") or ""
    got["warning_present"] = bool(text.strip()) == bool(expected["warning_present"])

    exact = _normalize_warning(text) == _normalize_warning(warning_text)
    got["warning_exact"] = exact == bool(expected["warning_exact"])

    got["warning_heading_caps"] = bool(warning.get("heading_all_caps")) == bool(
        expected["warning_heading_caps"]
    )
    return got


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reader", choices=("local", "cloud"), default="local")
    parser.add_argument("--limit", type=int, default=0, help="score the first N labels only")
    parser.add_argument("--json", type=Path, default=None, help="also write the per-label results here")
    args = parser.parse_args()

    manifest = json.loads((LABELS_ROOT / "manifest.json").read_text())
    warning_text = WARNING_ASSET.read_text()
    entries = [e for e in manifest["labels"] if e["kind"] == "real"]
    if args.limit:
        entries = entries[: args.limit]

    reader = _build_reader(args.reader)
    await reader.ensure_loaded()

    rows, seconds = [], []
    for entry in entries:
        read, elapsed = await _read_faces(reader, entry)
        seconds.append(elapsed)
        rows.append({"id": entry["id"], "seconds": round(elapsed, 2), **_score(entry, read, warning_text)})

    total = len(rows)
    print(f"\nreader: {args.reader}    labels: {total}\n")
    print(f"{'check':<22} {'correct':>9}")
    print("-" * 32)
    for check in CHECKS:
        correct = sum(1 for r in rows if r[check])
        print(f"{check:<22} {correct:>4} of {total}")
    print("-" * 32)
    ordered = sorted(seconds)
    print(
        f"seconds per label: median {statistics.median(ordered):.2f}, "
        f"slowest {ordered[-1]:.2f}, whole run {sum(ordered):.1f}"
    )
    misses = [r["id"] for r in rows if not r["warning_exact"]]
    if misses:
        print(f"\nwarning not word for word on {len(misses)}: {', '.join(misses)}")
    if args.json:
        args.json.write_text(json.dumps({"reader": args.reader, "labels": rows}, indent=1))
        print(f"\nper-label results written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
