"""Score a reader against the real labels and what is printed on them.

What it answers: on labels approved by TTB, how often does the reader report
the value the label itself carries?

    uv run python -m eval.read_accuracy                # the local reader
    uv run python -m eval.read_accuracy --reader cloud # needs OPENAI_API_KEY

The ground truth is the `label_observed` block of
`tests/fixtures/labels/manifest.json`: for each of 30 labels read out of the
TTB Public COLA Registry, a transcription of what the label prints, element by
element. The 8 variants derived from those labels by damaging the image or the
warning are not scored here; they exercise the rules, not the reader.

Nothing here is compared with the application the label was filed under. An
application is a second declaration about the same bottle, made on a form, and
it routinely differs from the label in ways that are nobody's misreading: the
application's origin field for a domestic product names a State ("KENTUCKY")
where the label prints "PRODUCT OF THE USA". Scoring a reader against it
measures the two records disagreeing, not the reader.

A check the label cannot settle is reported as not scoreable and left out of
that check's denominator, so a value nobody can compare against is not counted
against the reader. One label does this today: a keg collar printing four
volumes at once carries no single net-contents figure.

Two checks are shaped by what the reader reports against what the label
prints. The country of origin is scored on every label, domestic and imported
alike, including the 15 that print no origin statement, where the correct
reading is nothing; the reader reports a place name and the truth is the whole
printed statement, so the reading is looked for inside the statement. The name
and address is looked for the same way round, because the printed line carries
lead-in words the reader does not report ("AGED AND BOTTLED BY").

Every check uses the same comparison the rule pack uses, from
`app.rules._validators._helpers`, and net contents is converted with the rule
pack's own shipped unit table through `app.rules.units`, so a score here means
what a result in the running app means and a unit the app can read is never a
unit this harness scores as unreadable. The warning is the exception: it is
compared word for word after the normalization the rule pack pins to the
regulation text, because that is what 27 CFR 16.21 requires of it.

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
from functools import lru_cache
from pathlib import Path

from app.config import Settings
from app.rules._validators._helpers import normalize_words, word_run_present
from app.rules.units import UnitTable, millilitres, shipped_table
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

# A parenthesis in a transcription holds the transcriber's note, not printed
# words: "Double India Pale Ale (handwritten)" prints four words, not five.
_ANNOTATION_RE = re.compile(r"\([^)]*\)")


@lru_cache(maxsize=1)
def _units() -> UnitTable:
    """The unit table the running app uses, read once. `RULES_ROOT` picks the
    rule tree here exactly as it picks it for the app."""
    return shipped_table(Settings().rules_root)


def _millilitres(amount: object, unit: object) -> float | None:
    """One net-contents figure in millilitres, or None where there is no figure.

    The units and factors are the rule pack's own — `rules/tables/volume_units.yaml`,
    read through `app.rules.units` — so a spelling this harness scores as
    unreadable is exactly a spelling the running app cannot convert either.
    While the two carried separate lists they disagreed, and the harness scored
    a reader correct on a unit the app sent to a reviewer.

    Used for both sides. On the truth side None means the label prints no
    single figure to compare against, which makes the check not scoreable; on
    the reading side it means the reader returned nothing usable, which is a
    miss.
    """
    return millilitres(amount, unit, _units())


def _designations(printed: str | None) -> tuple[tuple[str, ...], ...]:
    """A printed element split into the designations a reader may report one of.

    A label often prints its class and type as several separate phrases —
    "TEQUILA", "100% BLUE AGAVE" and "REPOSADO" sit in three places on the same
    front label — and the manifest records them separated by "/". The reader
    returns the one line it found, so reporting any one of them is correct;
    demanding all of them in one run would score a perfect reading as a miss.
    """
    if not printed:
        return ()
    plain = _ANNOTATION_RE.sub(" ", printed)
    parts = (normalize_words(part) for part in plain.split("/"))
    return tuple(part for part in parts if part)


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


def _score(entry: dict, read: dict[str, dict], warning_text: str) -> dict[str, bool | None]:
    """Every check for one label: did the reader report what the label prints?

    True when the reader got it, False when it did not, and None when the label
    carries nothing to score the check against. None keeps that label out of
    the check's denominator instead of counting it as a reader miss.
    """
    observed = entry["label_observed"]
    got: dict[str, bool | None] = {}

    # The truth is the whole printed brand; the reader may return more around
    # it (a fanciful name on the same line), so the printed words must appear
    # in the reading as one run.
    brand_truth = normalize_words(observed["brand_name"] or "")
    brand_read = normalize_words((read.get("brand_name") or {}).get("brand_name") or "")
    got["brand"] = word_run_present(brand_read, brand_truth) if brand_truth else None

    class_read = normalize_words((read.get("class_type") or {}).get("class_type") or "")
    class_truth = _designations(observed["class_type"])
    got["class_type"] = (
        any(word_run_present(class_read, alt) for alt in class_truth)
        if class_truth
        else None
    )

    percent = (observed.get("abv") or {}).get("percent")
    abv_read = (read.get("abv") or {}).get("abv_pct")
    got["abv"] = (
        None if percent is None
        else abv_read is not None and abs(float(abv_read) - float(percent)) < 0.05
    )

    truth_net = observed.get("net_contents") or {}
    truth_ml = _millilitres(truth_net.get("amount"), truth_net.get("unit"))
    net = read.get("net_contents") or {}
    converted = _millilitres(net.get("net_contents_value"), net.get("unit"))
    got["net_contents"] = (
        None if truth_ml is None
        else converted is not None
        and abs(converted - truth_ml) <= max(1.0, truth_ml * 0.01)
    )

    # The printed line carries lead-in words the reader never reports ("AGED
    # AND BOTTLED BY"), so the reading's own anchor words are looked for in the
    # printed line rather than the other way round.
    name_read = read.get("name_address") or {}
    printed = normalize_words(
        ", ".join(str(name_read.get(k) or "").strip() for k in ("name", "city", "state"))
    )
    if observed["name_address"] is None:
        # A transcribed absence, not a gap: this label prints no bottler line
        # at all, so the correct reading is nothing.
        got["name_address"] = not printed
    else:
        block = normalize_words(observed["name_address"])
        anchors = [w for w in printed if len(w) > 3]
        got["name_address"] = bool(anchors) and any(
            word_run_present(block, (w,)) for w in anchors
        )

    # Scored on every label, not only the imported ones. Returning True for
    # free on a domestic label measured nothing on half the set, and 15 of
    # these labels print no origin statement, where the correct reading is
    # nothing — which is a reading the reader can get wrong.
    country_read = normalize_words((read.get("country_origin") or {}).get("country") or "")
    statement = observed["origin_statement"]
    if statement is None:
        got["origin"] = not country_read
    else:
        got["origin"] = bool(country_read) and word_run_present(
            normalize_words(statement), country_read
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


def _summarize(rows: list[dict], seconds: list[float], reader: str) -> None:
    """Print the scoreboard for one run.

    Its own function so it can be driven without a reader, an image or a model:
    `plans/step0_score_probe.py` scores every label off the manifest and prints
    through here, which is the only way this output gets exercised without
    spending the CPU budget a real run costs.
    """
    total = len(rows)
    print(f"\nreader: {reader}    labels: {total}\n")
    print(f"{'check':<22} {'correct of scoreable':>20}")
    print("-" * 44)
    for check in CHECKS:
        # A label the check cannot be scored on is out of the denominator, not
        # counted as a miss: it is the answer key that is silent, not the
        # reader that is wrong.
        scored = [r[check] for r in rows if r[check] is not None]
        correct = sum(1 for value in scored if value)
        unscoreable = total - len(scored)
        aside = f"   ({unscoreable} not scoreable)" if unscoreable else ""
        print(f"{check:<22} {correct:>8} of {len(scored):<3}{aside}")
    print("-" * 44)
    if seconds:
        ordered = sorted(seconds)
        print(
            f"seconds per label: median {statistics.median(ordered):.2f}, "
            f"slowest {ordered[-1]:.2f}, whole run {sum(ordered):.1f}"
        )
    misses = [r["id"] for r in rows if r["warning_exact"] is False]
    if misses:
        print(f"\nwarning not word for word on {len(misses)}: {', '.join(misses)}")


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

    _summarize(rows, seconds, args.reader)
    if args.json:
        args.json.write_text(json.dumps({"reader": args.reader, "labels": rows}, indent=1))
        print(f"\nper-label results written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
