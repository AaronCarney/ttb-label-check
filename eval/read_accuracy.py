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
from app.vision.local import freeze_reading, parse_reading, thaw_reading

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

# The words a printed origin statement uses to introduce the place, in the
# forms these labels print: "PRODUCT OF", "MADE IN THE", "HECHO EN",
# "DISTILLED IN", "BOTTLED BY". None of them is a place, so a reading made of
# nothing but these has not read the country. "a" is deliberately absent: it
# is a letter of "U.S.A." on the two labels that print the country that way.
_ORIGIN_LEAD_IN = frozenset(
    {"product", "of", "the", "made", "in", "hecho", "en", "distilled", "bottled",
     "by", "produced"}
)


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


def _recording_path(freeze_dir: Path, relative: str) -> Path:
    """Where one image's frozen reading lives, mirroring the corpus layout."""
    return (freeze_dir / relative).with_suffix(".json")


async def _read_one_face(
    reader, entry: dict, face: str, relative: str, freeze_dir: Path | None
) -> tuple[dict[str, dict], bool]:
    """One face's payloads, and whether they came off disk rather than the reader.

    With `--freeze`, an image whose recording already exists is not read again:
    the recording is thawed and parsed, which is the same parsing the reader
    does and costs no CPU. That is what makes a corpus pass restartable — stop
    it after any image and the next run picks up where it left off — and it is
    also why two labels sharing a face read it once.
    """
    path = LABELS_ROOT / relative
    if freeze_dir is not None:
        recording = _recording_path(freeze_dir, relative)
        if recording.exists():
            return parse_reading(thaw_reading(json.loads(recording.read_text()))), True

    label = Label(
        label_id=f"{entry['id']}-{face}",
        batch_id="read-accuracy",
        image_bytes=path.read_bytes(),
        content_type="image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png",
        face_tag="front" if face == "front" else "back",
    )
    # Cleared first so a recording is never written from the previous image:
    # a label the quality gate turns away never reaches the engine and produces
    # no reading at all.
    reader.last_reading = None
    payloads: dict[str, dict] = {}
    for observation in await reader.extract(label):
        if isinstance(observation.observed_value, dict):
            payloads[observation.field_id] = observation.observed_value

    if freeze_dir is not None:
        reading = getattr(reader, "last_reading", None)
        if reading is not None:
            recording = _recording_path(freeze_dir, relative)
            recording.parent.mkdir(parents=True, exist_ok=True)
            recording.write_text(
                json.dumps({"image": relative, **freeze_reading(reading)}, indent=1)
            )
    return payloads, False


async def _read_faces(
    reader, entry: dict, freeze_dir: Path | None = None
) -> tuple[dict[str, dict], float, int]:
    """Read every face of one label; return the merged payloads, the seconds and
    how many of its faces came from a recording rather than from the reader.

    A label's elements are spread over its faces, and the front carries the
    ones the regulations put in the same field of vision, so the faces are read
    front first and the first face reporting a value for a field is the one
    that holds it. The warning is taken from whichever face carries it.
    """
    merged: dict[str, dict] = {}
    started = time.perf_counter()
    replayed = 0
    faces = sorted(
        entry["images"].items(),
        key=lambda kv: ("front", "back", "neck", "side").index(kv[0])
        if kv[0] in ("front", "back", "neck", "side") else 9,
    )
    for face, relative in faces:
        if not (LABELS_ROOT / relative).exists():
            continue
        payloads, from_recording = await _read_one_face(
            reader, entry, face, relative, freeze_dir
        )
        replayed += int(from_recording)
        for field_id, payload in payloads.items():
            if _has_reading(merged.get(field_id)):
                continue
            if _has_reading(payload):
                merged[field_id] = payload
            else:
                merged.setdefault(field_id, payload)
    return merged, time.perf_counter() - started, replayed


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
        # Two of the reading's words, adjacent in the reading and adjacent in
        # the printed line. One shared word was enough before, which is not
        # evidence the reader found the line: these lines carry a city, a State
        # and words like "COMPANY" and "IMPORTS" that a reading of some other
        # part of the label lands on by itself.
        got["name_address"] = any(
            word_run_present(block, printed[i:i + 2]) for i in range(len(printed) - 1)
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
        # The place, not the lead-in. The reading is still looked for inside the
        # whole statement, because one label names its country in the middle of
        # a bottler line. But a reading made only of the words that introduce
        # the place - "PRODUCT OF" - names no place and is not a reading of one.
        place = tuple(w for w in country_read if w not in _ORIGIN_LEAD_IN)
        got["origin"] = bool(place) and word_run_present(
            normalize_words(statement), place
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


def _summarize(
    rows: list[dict], seconds: list[float], reader: str, replayed: int = 0, read: int = 0
) -> None:
    """Print the scoreboard for one run.

    Its own function so it can be driven without a reader, an image or a model:
    `plans/step0_score_probe.py` scores every label off the manifest and prints
    through here, which is the only way this output gets exercised without
    spending the CPU budget a real run costs.
    """
    total = len(rows)
    print(f"\nreader: {reader}    labels: {total}\n")
    if replayed or read:
        # Where the readings came from, because the denominator is the thing a
        # reader of this scoreboard can most easily get wrong. A replayed face
        # is this same reader's own output over the same image, recorded on an
        # earlier run; it is not a stub and it is not a second reader.
        print(f"faces read now: {read}    faces replayed from recordings: {replayed}\n")
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
    # Naming what the False actually means. `warning_exact` scores the reader's
    # verdict against the label's, so a False is the reader disagreeing with the
    # label - which happens both on a label whose warning is word for word and
    # on one whose warning is not. Reporting these as labels whose warning is
    # not word for word stated the opposite of the truth for the second kind.
    misses = [r["id"] for r in rows if r["warning_exact"] is False]
    if misses:
        print(f"\nword-for-word verdict wrong on {len(misses)}: {', '.join(misses)}")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reader", choices=("local", "cloud"), default="local")
    parser.add_argument("--limit", type=int, default=0, help="score the first N labels only")
    parser.add_argument(
        "--only",
        default="",
        help=(
            "walk these manifest ids instead of every real label, comma separated. "
            "Which labels are worth reading first is a question of what they can "
            "prove, not of where they sit in the file, and --limit can only take "
            "the head of the list. Variants may be named here: they are read and "
            "recorded, and still not scored."
        ),
    )
    parser.add_argument(
        "--freeze",
        type=Path,
        default=None,
        help=(
            "record each image's reading here as JSON, and replay an image whose "
            "recording already exists instead of reading it again. Makes a corpus "
            "pass restartable and gives the replay suite its fixtures."
        ),
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help=(
            "wait this many seconds after each label that was actually read, to "
            "let the CPU cool between labels. A label served entirely from "
            "recordings spent no CPU, so it is not followed by a wait, and "
            "neither is the last label."
        ),
    )
    parser.add_argument("--json", type=Path, default=None, help="also write the per-label results here")
    args = parser.parse_args()

    manifest = json.loads((LABELS_ROOT / "manifest.json").read_text())
    warning_text = WARNING_ASSET.read_text()

    if args.only:
        wanted = [name.strip() for name in args.only.split(",") if name.strip()]
        by_id = {e["id"]: e for e in manifest["labels"]}
        missing = [name for name in wanted if name not in by_id]
        if missing:
            raise SystemExit(f"--only names labels the manifest does not carry: {', '.join(missing)}")
        entries = [by_id[name] for name in wanted]
    else:
        entries = [e for e in manifest["labels"] if e["kind"] == "real"]
    if args.limit:
        entries = entries[: args.limit]

    if args.freeze is not None and args.reader != "local":
        raise SystemExit("--freeze records the local reader's own boxes; it has nothing to record for --reader cloud.")

    reader = _build_reader(args.reader)
    await reader.ensure_loaded()

    rows, seconds = [], []
    faces_replayed = faces_read = 0
    for position, entry in enumerate(entries):
        read, elapsed, replayed = await _read_faces(reader, entry, args.freeze)
        faces_replayed += replayed
        read_now = len(entry["images"]) - replayed
        faces_read += read_now
        # The cooling gap belongs after work, so it is skipped for a label whose
        # faces all came off disk and after the last label, where waiting delays
        # the scoreboard and cools nothing.
        if args.sleep > 0 and read_now > 0 and position + 1 < len(entries):
            await asyncio.sleep(args.sleep)
        # A variant is a damaged copy of a real label: it exercises the rules,
        # not the reader, so it is recorded but never scored.
        if entry["kind"] != "real":
            continue
        seconds.append(elapsed)
        rows.append({"id": entry["id"], "seconds": round(elapsed, 2), **_score(entry, read, warning_text)})

    _summarize(rows, seconds, args.reader, replayed=faces_replayed, read=faces_read)
    if args.json:
        args.json.write_text(json.dumps({"reader": args.reader, "labels": rows}, indent=1))
        print(f"\nper-label results written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
