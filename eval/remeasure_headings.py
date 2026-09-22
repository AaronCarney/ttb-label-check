"""Measure the warning heading again in every frozen reading, from its image.

A frozen reading holds the boxes the OCR returned and the heading measurement
taken from the pixels afterwards. The boxes cost an OCR pass to renew; the
measurement costs a crop. So when the measurement changes, this brings every
frozen reading up to date with the code without reading any text again.

    uv run python -m eval.remeasure_headings           # report what would change
    uv run python -m eval.remeasure_headings --write   # and write it

It reads the corpus recordings in `tests/recordings/reader/` and, where they
have been fetched, the held-out readings in `eval/data/registry-readings/`.
Nothing but `heading_measurement` is rewritten.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.vision.local import freeze_reading, remeasure_heading, thaw_reading
from eval.corpus_check import LABELS_ROOT, RECORDINGS_ROOT, REGISTRY_READINGS


def _image_of(recording: Path, data: dict) -> Path:
    """The image a reading was taken from. Corpus recordings name it relative
    to the labels folder; held-out readings name it from the repository root."""
    named = Path(data["image"])
    return named if named.exists() else LABELS_ROOT / named


def remeasure(roots: list[Path], write: bool) -> tuple[int, list[Path]]:
    """How many readings were looked at, and those whose measurement changed."""
    seen = 0
    changed: list[Path] = []
    for root in roots:
        for recording in sorted(root.rglob("*.json")):
            data = json.loads(recording.read_text())
            if "heading_measurement" not in data:
                continue
            seen += 1
            reading = remeasure_heading(_image_of(recording, data).read_bytes(), thaw_reading(data))
            fresh = freeze_reading(reading)["heading_measurement"]
            if fresh == data["heading_measurement"]:
                continue
            changed.append(recording)
            print(f"{recording}: {data['heading_measurement']} -> {fresh}")
            if write:
                data["heading_measurement"] = fresh
                recording.write_text(json.dumps(data, indent=1))
    return seen, changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="write the new measurements")
    args = parser.parse_args()
    roots = [RECORDINGS_ROOT] + ([REGISTRY_READINGS] if REGISTRY_READINGS.exists() else [])
    seen, changed = remeasure(roots, args.write)
    verb = "rewritten" if args.write else "would change"
    print(f"{len(changed)} of {seen} readings {verb}")


if __name__ == "__main__":
    main()
