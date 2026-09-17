"""LocalVisionExtractor — reads a label without an outbound call.

The default reader (decision 0005). It runs a CPU OCR engine inside this
process, so a clone checks labels out of the box, with no key and no account,
and the product works inside a network that blocks outbound traffic.

**It reports; it does not decide.** Every reading it emits is what the OCR
engine returned, trimmed to the field it belongs to. Nothing here corrects a
label: a warning that reads "ALOHOLIC" is reported that way, and the rule pack
settles what that means.

**Its output is interchangeable with the hosted reader's.** It emits the same
seven `field_id`s carrying the same payload keys as `app.vision.cloud`, so the
rule engine, the evaluator and the wire envelope treat the two identically.
Each of the seven is always emitted, with an empty reading where nothing was
found, because an observation that is absent makes the rule asking for it skip
in silence rather than fail.

**Where it is weaker, it says so.** Plain OCR returns lines of text, not
labelled fields, so brand, class/type and the name-and-address block are picked
out by layout and wording. Each reading carries a confidence that reflects how
definite that pick was, and a field it could not find carries zero.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import threading
import time
import unicodedata
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO

import numpy as np
from PIL import Image

from app.config import Settings
from app.rules._validators._helpers import normalize_words, word_run_present
from app.rules.units import UnitTable, millilitres, millilitres_from_text, shipped_table
from app.schemas.calls import CallRecord
from app.schemas.expected import BeverageClass
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.label import Label
from app.vision import quality
from app.vision.heading_measure import HeadingMeasurement, measure_heading_bold_image

_logger = logging.getLogger("app.vision.local")


# The longest edge any image is scaled down to before reading. Label
# photographs from the registry run to several thousand pixels, and the
# detection model gains nothing above this while costing time on every one.
MAX_EDGE_PX = 1600

# How definite each field's pick is, applied to the OCR engine's own character
# confidence for the boxes the reading came from. A regex over the text either
# matched or did not, so those fields keep almost all of it; a field chosen by
# how large its type is, or by the words in front of it, keeps less.
_PICK_CERTAINTY = {
    "brand_name": 0.75,
    "class_type": 0.85,
    "abv": 0.95,
    "net_contents": 0.95,
    "gov_warning": 1.00,
    "name_address": 0.80,
    "country_origin": 0.95,
}

# Reading the warning out of a frame the image had to be rotated into is a
# weaker result than reading it as it lay, so it is reported as one.
_ROTATED_FRAME_PENALTY = 0.90

_FIELD_NAMES = (
    "brand_name",
    "class_type",
    "abv",
    "net_contents",
    "gov_warning",
    "name_address",
    "country_origin",
)


# ---------------------------------------------------------------------------
# What the OCR engine gives back
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Box:
    """One block of text the engine found, and where it sat."""

    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    score: float

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2.0

    def as_bbox(self) -> tuple[int, int, int, int]:
        return (int(self.x0), int(self.y0), int(self.x1), int(self.y1))


@dataclass(frozen=True)
class _Reading:
    """Everything the engine and the pixels gave back, before any parsing.

    This is the seam the frozen recordings sit on. Everything above it needs an
    image, an OCR engine and a second of CPU; everything below it — `_parse` and
    the seven field extractors — is a pure function of what is in here. Freezing
    one of these turns the parsing layer into something a test can drive in
    milliseconds with no model, no image and no network.

    `warning_boxes` is a separate list because the warning is not always read
    from the upright frame: a label photographed on its side is tried at 90° and
    270°, and the frame that finds the heading is the frame the statement is read
    from. A recording that kept only the upright pass would lose it.
    """

    boxes: list[_Box]
    warning_boxes: list[_Box]
    rotation: int
    heading_measurement: HeadingMeasurement | None
    frame_size: tuple[int, int]


FROZEN_SCHEMA_VERSION = 1


def freeze_reading(reading: _Reading) -> dict:
    """One reading as plain JSON-safe data."""
    def box(b: _Box) -> dict:
        return {
            "box": [round(b.x0, 2), round(b.y0, 2), round(b.x1, 2), round(b.y1, 2)],
            "text": b.text,
            "score": round(b.score, 4),
        }

    measurement = reading.heading_measurement
    return {
        "schema_version": FROZEN_SCHEMA_VERSION,
        "frame_size": list(reading.frame_size),
        "rotation_deg": reading.rotation,
        "boxes": [box(b) for b in reading.boxes],
        # Written out even when it is the same list as `boxes`, so a reader of
        # the file never has to know the rule that decides when it differs.
        "warning_boxes": [box(b) for b in reading.warning_boxes],
        "heading_measurement": None if measurement is None else {
            "is_bold": measurement.is_bold,
            "mean_stroke_width": round(measurement.mean_stroke_width, 4),
            "mean_character_height": round(measurement.mean_character_height, 4),
            "width_height_ratio": round(measurement.width_height_ratio, 4),
            "confident": measurement.confident,
        },
    }


def thaw_reading(data: dict) -> _Reading:
    """A frozen reading back into the objects `_parse` takes."""
    if data.get("schema_version") != FROZEN_SCHEMA_VERSION:
        raise ValueError(
            f"frozen reading schema {data.get('schema_version')!r}, "
            f"expected {FROZEN_SCHEMA_VERSION}"
        )

    def box(raw: dict) -> _Box:
        x0, y0, x1, y1 = raw["box"]
        return _Box(x0=x0, y0=y0, x1=x1, y1=y1, text=raw["text"], score=raw["score"])

    measurement = data["heading_measurement"]
    return _Reading(
        boxes=[box(b) for b in data["boxes"]],
        warning_boxes=[box(b) for b in data["warning_boxes"]],
        rotation=int(data["rotation_deg"]),
        heading_measurement=None if measurement is None else HeadingMeasurement(
            is_bold=measurement["is_bold"],
            mean_stroke_width=measurement["mean_stroke_width"],
            mean_character_height=measurement["mean_character_height"],
            width_height_ratio=measurement["width_height_ratio"],
            confident=measurement["confident"],
        ),
        frame_size=tuple(data["frame_size"]),
    )


def parse_reading(reading: _Reading) -> dict[str, dict]:
    """The seven field payloads a reading produces, keyed by field.

    The production path itself, minus the pixels: `extract` reports exactly
    these payloads. It is what the replay suite drives and what scores a frozen
    recording.
    """
    return {field: payload for field, (payload, _bbox, _text) in _parse(
        boxes=reading.boxes,
        warning_boxes=reading.warning_boxes,
        rotation=reading.rotation,
        heading_measurement=reading.heading_measurement,
    ).items()}


def _fold(text: str) -> str:
    """One string reduced for matching only: accents dropped, case folded.

    Used to find a phrase, never to report one. What is reported is always the
    text the engine returned.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).upper()


_HEADING_RE = re.compile(r"GOVERNMENT\s*WARNING", re.I)
_HEADING_WORD1_RE = re.compile(r"^\W*GOVERNMENT\W*$", re.I)
_HEADING_WORD2_RE = re.compile(r"^\W*WARNING\b", re.I)
_BLOCK_END_RE = re.compile(r"HEALTH\s*PROBLEMS\s*[.,]?", re.I)

# A barcode's digits sit beside justified warning text often enough to be
# swept into the block, and the engine reads its bars as stray punctuation.
# A run that is mostly digits and holds no word is not label text.
_BARCODE_RE = re.compile(r"^[\s\d|\"'.,>\-]{8,}$")


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------

class LocalVisionExtractor:
    """Reads one label image with a CPU OCR engine and reports seven fields."""

    def __init__(self, *, settings: Settings, ring_buffer: deque) -> None:
        self._settings = settings
        self._ring = ring_buffer
        self._engine = None
        self.last_reading: _Reading | None = None
        # One reader serves the whole process (``app/deps.py``), so these guard
        # against callers in different requests, and the requests run in
        # different event loops across a process's life. Both locks are
        # threading locks, held inside the worker thread, because an
        # ``asyncio.Lock`` binds to the first loop that awaits it and refuses
        # the next one.
        self._load_lock = threading.Lock()
        self._read_lock = threading.Lock()

    # -- lifecycle ---------------------------------------------------------

    def _thread_cap(self) -> int:
        """How many CPU threads this reader may use, inside the window the
        engine will actually accept.

        rapidocr applies a thread setting only when ``1 <= n <= os.cpu_count()``
        (``rapidocr/inference_engine/onnxruntime/main.py``). A value outside that
        window is dropped with no error and no log line, and the engine then
        takes every core on the machine — the failure this cap exists to
        prevent. So the configured number is clamped into the window here
        rather than passed through and silently ignored.
        """
        available = os.cpu_count() or 1
        return max(1, min(int(self._settings.ocr_num_threads), available))

    def _load(self) -> object:
        """Build the engine, held to its thread cap. Blocking: the models are
        read off disk.

        Three libraries decide how much of the machine one read lights up, and
        capping one leaves the others wide:

        * **onnxruntime** runs the three models. Its two thread counts are set
          at construction, which is the only opportunity — all three
          ``InferenceSession`` objects are built before ``RapidOCR.__init__``
          returns. It links no OpenMP, so ``OMP_NUM_THREADS`` governs nothing
          here however plausible it looks.
        * **OpenCV** resizes every image on the way in, and reads
          ``setNumThreads`` rather than any environment variable. Left alone it
          runs one thread per core.
        * **OpenBLAS**, underneath OpenCV and NumPy, reads ``OPENBLAS_NUM_THREADS``
          when the library loads, which is before any code here runs — this
          module imports NumPy and pulls in OpenCV at import time. So that one
          cannot be set from here at all: it belongs in the process environment,
          and the container image is where the deployed product sets it.
        """
        threads = self._thread_cap()

        import cv2

        cv2.setNumThreads(threads)

        from rapidocr import RapidOCR

        engine = RapidOCR(
            params={
                "EngineConfig.onnxruntime.intra_op_num_threads": threads,
                "EngineConfig.onnxruntime.inter_op_num_threads": threads,
            }
        )
        _logger.info(
            "ocr_engine_loaded",
            extra={
                "requested_threads": self._settings.ocr_num_threads,
                "effective_threads": threads,
                "cv2_threads": cv2.getNumThreads(),
            },
        )
        return engine

    async def ensure_loaded(self) -> None:
        """Load the models before a read rather than during one.

        The load costs about a second and blocks, so it runs in a worker thread
        behind a lock: whoever gets there second waits on the one load instead
        of building a second engine. ``app/deps.py`` hands the whole process one
        reader, so this is paid once per process, and ``/healthz`` can pay it
        before any label arrives.
        """
        if self._engine is not None:
            return
        await asyncio.to_thread(self._load_once)

    def _load_once(self) -> None:
        """Build the engine unless another thread already did. Blocking."""
        with self._load_lock:
            if self._engine is None:
                self._engine = self._load()

    # -- reading -----------------------------------------------------------

    def _boxes(self, image: Image.Image) -> list[_Box]:
        result = self._engine(np.array(image))
        if result is None or result.txts is None:
            return []
        scores = result.scores if result.scores is not None else [1.0] * len(result.txts)
        boxes: list[_Box] = []
        for quad, text, score in zip(result.boxes.tolist(), result.txts, scores):
            xs = [p[0] for p in quad]
            ys = [p[1] for p in quad]
            boxes.append(
                _Box(
                    x0=min(xs), x1=max(xs), y0=min(ys), y1=max(ys),
                    text=str(text), score=float(score),
                )
            )
        return boxes

    async def extract(self, label: Label) -> list[FieldObservation]:
        report = quality.assess(label)
        if report.disposition != "ok":
            return [
                FieldObservation(
                    field_id="quality",
                    beverage_class=BeverageClass.SPIRITS,
                    observed_value=None,
                    evidence=(
                        Evidence(
                            field_id="quality",
                            source=EvidenceSource.DERIVED,
                            bbox=None,
                            extracted_text=report.reason_code,
                            match_kind=MatchKind.NONE,
                            confidence=0.0,
                        ),
                    ),
                    upstream_meta={
                        "disposition": report.disposition,
                        "reason_code": report.reason_code,
                    },
                )
            ]

        await self.ensure_loaded()
        t0 = time.monotonic()
        payloads, meta = await asyncio.to_thread(self._read_serialised, label.image_bytes)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        self._record(label=label, payloads=payloads, meta=meta, elapsed_ms=elapsed_ms)

        observations: list[FieldObservation] = []
        for field_name in _FIELD_NAMES:
            payload, bbox, text = payloads[field_name]
            observations.append(
                FieldObservation(
                    field_id=field_name,
                    beverage_class=BeverageClass.SPIRITS,
                    observed_value=payload,
                    evidence=(
                        Evidence(
                            field_id=field_name,
                            source=EvidenceSource.OCR,
                            bbox=bbox,
                            extracted_text=text,
                            match_kind=MatchKind.NONE,
                            confidence=float(payload.get("confidence", 0.0)),
                        ),
                    ),
                    upstream_meta={"bbox": bbox, **meta},
                )
            )
        return observations

    def _record(self, *, label: Label, payloads: dict, meta: dict, elapsed_ms: int) -> None:
        readable = {k: v[0] for k, v in payloads.items()}
        self._ring.append(
            CallRecord(
                ts=datetime.now(timezone.utc),
                batch_id=label.batch_id,
                label_id=label.label_id,
                stage="vision.local_ocr",
                request={"call_kind": "local_ocr", "image_size": len(label.image_bytes)},
                response=readable,
                latency_ms=elapsed_ms,
                model="PP-OCRv6-small",
                provider="local.rapidocr",
                prompt_version=None,
                output_hash=hashlib.sha256(
                    json.dumps(readable, sort_keys=True, default=str).encode()
                ).hexdigest()[:16],
            )
        )

    # -- the pipeline, off the event loop ----------------------------------

    def _read_serialised(self, image_bytes: bytes) -> tuple[dict, dict]:
        """Read one image, one at a time. Blocking; runs in a worker thread.

        The process shares one engine (``app/deps.py``), and the OCR library
        makes no promise about being called from two threads at once, so reads
        queue rather than overlap. On a machine reading labels this also keeps
        one OCR pass on the CPU at a time instead of several.
        """
        with self._read_lock:
            return self._read(image_bytes)

    def look(self, image_bytes: bytes) -> _Reading:
        """Everything one image gives the engine, before any parsing.

        Blocking, and the expensive half of a read: the detector runs here, up
        to three times on a label photographed on its side. Separated from the
        parsing so a reading can be frozen and replayed — see `_Reading`.
        """
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        if max(image.size) > MAX_EDGE_PX:
            image.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX))
        boxes = self._boxes(image)

        # A label photographed on its side reads as nothing at all. Where no
        # warning heading is found, the image is tried on its side both ways,
        # and the frame that finds one is the frame the warning is read from.
        warning_boxes = boxes
        rotation = 0
        warning_image = image
        found = _find_heading(boxes)
        if found is None:
            for angle in (90, 270):
                rotated = image.rotate(angle, expand=True)
                candidate = self._boxes(rotated)
                candidate_heading = _find_heading(candidate)
                if candidate_heading is not None:
                    warning_boxes, rotation, warning_image = candidate, angle, rotated
                    found = candidate_heading
                    break

        # The heading's boldness is measured here rather than inside `_parse`,
        # for two reasons that pull the same way. It is the one step of the
        # reading that needs pixels, so taking it here leaves `_parse` a pure
        # function of the boxes — testable against a frozen reading with no
        # image, no model and no network. And it is measured on `warning_image`,
        # the frame the boxes were actually computed from: the bbox is in that
        # frame's pixel space, and the measurement does not rescale, so handing
        # it the original full-size image would crop the wrong part of a label
        # that was downscaled on the way in and report a real stroke width about
        # the wrong pixels.
        heading_measurement = (
            measure_heading_bold_image(warning_image, found[0].as_bbox())
            if found is not None
            else None
        )

        return _Reading(
            boxes=boxes,
            warning_boxes=warning_boxes,
            rotation=rotation,
            heading_measurement=heading_measurement,
            frame_size=image.size,
        )

    def _read(self, image_bytes: bytes) -> tuple[dict, dict]:
        """OCR one image and cut its text into the seven fields.

        Returns the per-field payloads and a small record of how the read went,
        which the audit trail carries.
        """
        reading = self.look(image_bytes)
        # Kept so the pass that reads a label can also record what it saw,
        # rather than a recording costing a second pass over the same image.
        # Reads are serialised on `_read_lock`, so this is the reading of the
        # call that has just returned. Nothing in the app reads it.
        self.last_reading = reading
        payloads = _parse(
            boxes=reading.boxes,
            warning_boxes=reading.warning_boxes,
            rotation=reading.rotation,
            heading_measurement=reading.heading_measurement,
        )
        meta = {
            "reader": "local",
            "engine": "rapidocr",
            "rotation_deg": reading.rotation,
            "boxes_found": len(reading.boxes),
        }
        return payloads, meta


# ---------------------------------------------------------------------------
# Cutting the text into fields
# ---------------------------------------------------------------------------

def _find_heading(boxes: list[_Box]) -> tuple[_Box, list[_Box]] | None:
    """The government-warning heading, and the boxes that spell it.

    The engine returns the heading as one block on most labels and splits it
    across two on some, so both are looked for.
    """
    for box in boxes:
        if _HEADING_RE.search(_fold(box.text)):
            return box, [box]
    for box in boxes:
        if not _HEADING_WORD1_RE.match(_fold(box.text)):
            continue
        for other in boxes:
            if other is box:
                continue
            same_line = abs(other.cy - box.cy) < box.height * 0.7
            to_the_right = other.x0 >= box.x0
            if same_line and to_the_right and _HEADING_WORD2_RE.match(_fold(other.text)):
                return box, [box, other]
    return None


def _columns(boxes: list[_Box]) -> list[list[_Box]]:
    """Split boxes into columns where a clear vertical gutter separates them.

    A keg collar sets the warning in two columns. Reading such a block by rows
    interleaves the two and produces a sentence that is in neither.
    """
    if len(boxes) < 4:
        return [boxes]
    left = min(b.x0 for b in boxes)
    right = max(b.x1 for b in boxes)
    span = right - left
    if span <= 0:
        return [boxes]

    # Walk the x axis and find a run wide enough to be a gutter that no box
    # crosses. A gutter under a twelfth of the block's width is word spacing.
    covered = np.zeros(int(span) + 1, dtype=bool)
    for b in boxes:
        covered[int(b.x0 - left):int(b.x1 - left) + 1] = True
    gutter_min = max(int(span * 0.08), 8)
    gutters: list[tuple[int, int]] = []
    run_start = None
    for i, filled in enumerate(covered):
        if not filled and run_start is None:
            run_start = i
        elif filled and run_start is not None:
            if i - run_start >= gutter_min:
                gutters.append((run_start, i))
            run_start = None
    if not gutters:
        return [boxes]

    cuts = [left] + [left + (g[0] + g[1]) / 2.0 for g in gutters] + [right + 1]
    columns: list[list[_Box]] = []
    for lo, hi in zip(cuts, cuts[1:]):
        column = [b for b in boxes if lo <= (b.x0 + b.x1) / 2.0 < hi]
        if column:
            columns.append(column)
    return columns or [boxes]


def _reading_order(boxes: list[_Box]) -> list[_Box]:
    """Boxes in the order a person reads them: column by column, row by row."""
    ordered: list[_Box] = []
    for column in _columns(boxes):
        line_height = max((b.height for b in column), default=1.0) or 1.0
        ordered.extend(
            sorted(column, key=lambda b: (round(b.y0 / (line_height * 0.7)), b.x0))
        )
    return ordered


def _boxes_spanning(parts: list[str], cutoff: int) -> int:
    """How many of these box texts it takes to reach `cutoff` in their join.

    The join is rebuilt the same way the block's text is — one space between
    parts, runs of whitespace collapsed — so the count is exact rather than an
    estimate from character offsets. A box the cutoff falls inside is counted:
    it did contribute words to the statement.
    """
    running = ""
    for index, part in enumerate(parts):
        running = re.sub(r"\s+", " ", f"{running} {part}").strip()
        if len(running) >= cutoff:
            return index + 1
    return len(parts)


def _warning_block(boxes: list[_Box]) -> tuple[str, str, _Box, list[_Box]] | None:
    """The warning's text, its heading, the heading's box and the block's boxes.

    The block is the heading plus what runs on beneath it, stopping at the
    first vertical gap too large to be a line break and at the statement's own
    last words.
    """
    found = _find_heading(boxes)
    if found is None:
        return None
    heading, heading_boxes = found
    line_height = heading.height or 1.0

    # Everything at or below the heading, discarding a barcode's digits.
    below = [
        b for b in boxes
        if b.y1 >= heading.y0 - line_height * 0.6
        and not _BARCODE_RE.match(b.text.strip())
    ]

    # Stop where the text stops running on. A gap of more than two and a half
    # lines is the next thing on the label, not the next line of the warning.
    block: list[_Box] = []
    last_bottom: float | None = None
    for b in sorted(below, key=lambda b: b.y0):
        if last_bottom is not None and b.y0 - last_bottom > line_height * 2.5:
            break
        block.append(b)
        last_bottom = max(last_bottom or 0.0, b.y1)

    ordered = _reading_order(block)

    # The statement begins at its own heading. A box sitting above the heading
    # or beside it carries other label text — a phone number, an origin
    # statement, the line the heading was printed under — and the sweep above
    # picks such boxes up because they sit within a line of the heading. Every
    # box before the heading in reading order is dropped, and where the engine
    # merged that text into the heading's own box, the box is cut at the
    # heading too.
    start = next(
        (i for i, b in enumerate(ordered) if _HEADING_RE.search(_fold(b.text))),
        None,
    )
    if start is None:
        start = next((i for i, b in enumerate(ordered) if b is heading), 0)
    ordered = ordered[start:]
    spoken = [b for b in ordered if b.text.strip()]
    parts = [b.text for b in spoken]
    if parts:
        opening = re.search(r"GOVERNMENT\s*WARNING", parts[0], re.I)
        if opening:
            parts[0] = parts[0][opening.start():]
    text = re.sub(r"\s+", " ", " ".join(parts)).strip()

    # The statement ends at its own last words, and the **boxes** end there
    # too. `_parse` subtracts this box list from the body before it looks for
    # any other element, so a box kept here is a box no other field can be read
    # from. Trimming only the text left the label's own lines inside the block:
    # measured over the frozen slice, that threw away `12% ALC. BY VOL.`,
    # `750 ML`, `PRODUCT OF ITALY` and an importer's name and city, each of
    # which the engine had read correctly and none of which the warning
    # contains.
    end = _BLOCK_END_RE.search(text)
    if end:
        text = text[: end.end()]
        ordered = spoken[: _boxes_spanning(parts, end.end())]

    heading_text = " ".join(b.text for b in heading_boxes).strip()
    match = re.search(r"WARNING\s*[:：]?", _fold(heading_text))
    if match:
        heading_text = heading_text[: match.end()]
    return text, heading_text.strip(), heading, ordered


_ABV_RE = re.compile(
    r"(?:ALC(?:OHOL)?\.?\s*(?:BY\s*VOL\.?\s*)?[:\s]*)?"
    r"(\d{1,2}(?:[.,]\d{1,2})?)\s*%"
    r"|"
    r"(?:ALC(?:OHOL)?\.?\s*)(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:%|DEGREES?)?\s*(?:BY\s*)?VOL",
    re.I,
)
# The alcohol statement as the label prints it, which is a different question
# from what the percentage is. `_ABV_RE` finds the figure; this finds the words
# around it, in either of the orders a label uses — "ALCOHOL 40% BY VOLUME" and
# "40% ALC. BY VOL." are both printed, and 27 CFR §5.65(b) is about exactly that
# form of words. A label that prints a bare "12.5%" yields a bare "12.5%", which
# is the fact the format rule needs rather than a hole in the payload.
_ALC_STATEMENT_RE = re.compile(
    r"(?:ALC(?:OHOL)?\.?\s*)?"
    r"\d{1,2}(?:[.,]\d{1,2})?\s*%?"
    r"(?:\s*(?:ALC(?:OHOL)?\.?)?\s*(?:BY\s*VOL(?:UME)?|/\s*VOL|VOL)\.?)?",
    re.I,
)
# The net-contents units, and the one table that lists them.
#
# The list used to be written out here, and it was the fourth copy in the app:
# it knew `ML` and `FL. OZ.` but not `FL. OUNCES`, `FLUID OUNCES`, `MILLILITRES`
# or `US GALLONS`, all of which `rules/tables/volume_units.yaml` lists and all of
# which real labels in this corpus print. A unit missing from here produced **no
# net-contents reading at all**, so `11.2 FL. OUNCES` and a `15.5 US GALLONS` keg
# collar read as nothing while the rule pack, the application form and the
# accuracy harness all converted them happily. Adding a unit is now an edit to
# that one YAML file.


@lru_cache(maxsize=1)
def _units() -> UnitTable:
    """The unit table the running app converts by, read once.

    `RULES_ROOT` picks the rule tree here exactly as it picks it for the app,
    which is what `eval/read_accuracy.py` does with the same table. Reading it
    costs one file read on the first parse and nothing after: it is data, not an
    image, so `_parse` stays replayable with no picture and no socket.
    """
    return shipped_table(Settings().rules_root)


@lru_cache(maxsize=1)
def _net_re() -> re.Pattern[str]:
    """A number and the unit written next to it, for every unit the table lists.

    The table's own rule is that "a unit is matched on its letters and digits
    alone, because a label and a reader each spell it as they find it" — so each
    listed unit becomes its characters joined by "anything that is not a letter
    or a digit", which is what makes `FL. OZ.`, `FL OZ` and `fl.oz` one entry.
    That is the same reduction `app.rules.units.unit_key` performs, expressed as
    a pattern so the reader can find the unit in a line of label text.

    Longest listed unit first, so `15.5 LITERS` is read as litres rather than as
    a bare `L` with `ITERS` left over, and the match may not run on into another
    word.
    """
    keys = sorted(_units().factors, key=len, reverse=True)
    if not keys:
        # No rule tree, so no unit converts. A pattern that matches nothing is
        # the honest reading: every net contents goes to a reviewer.
        return re.compile(r"(?!)")
    separator = r"[^0-9A-Za-z]*"
    spellings = (separator.join(re.escape(ch) for ch in key) for key in keys)
    return re.compile(
        r"(\d+(?:[.,]\d+)?)\s*(" + "|".join(spellings) + r")(?![0-9A-Za-z])",
        re.I,
    )


def _net_reading(text: str) -> tuple[re.Match, float] | None:
    """The one net-contents figure a line declares, or None for a reviewer.

    A line often carries the same quantity twice — `NET CONT. 350 ML / 12 FL OZ`
    — and taking whichever the box order happened to put first took the rounded
    customary figure as often as the metric one. Which figure is *the*
    declaration is settled by `app.rules.units.millilitres_from_text`, the same
    function the application form settles it with, so the two sides of a
    comparison can no longer disagree about what the label declared.

    Returning None where that function does is the point of it rather than a
    gap: `1 PT. 9 FL. OZ.` names two figures that are not one quantity and that
    nothing here can add up, so the reader declares nothing and a reviewer
    reads the words. It used to report `1 PT` — a pint, against a bottle that
    holds nearly a pint and a half.

    The figure is returned as the label prints it, with its printed unit, not
    converted: the rule pack allows a customary size and its rounded metric
    equivalent to agree within a tolerance it carries itself, and a reader that
    handed it millilitres would collapse that tolerance to nothing and reject
    compliant labels.
    """
    table = _units()
    matches = list(_net_re().finditer(text))
    if not matches:
        return None
    declared = millilitres_from_text(text, table)
    if declared is None:
        return None
    for match in matches:
        amount = float(match.group(1).replace(",", "."))
        value = millilitres(amount, match.group(2), table)
        if value is None:
            continue
        if abs(value - declared) <= 1e-9 * max(abs(declared), 1.0):
            return match, amount
    return None


def _net_contents(boxes: list[_Box]) -> tuple[_Box, re.Match, float] | None:
    """The first line in reading order that declares one net-contents figure.

    A line that names a figure this reader cannot resolve to one quantity is
    passed over rather than ending the search, the same way `_first_match`
    carries on past a match its `reject` turns down.
    """
    for box in _reading_order(boxes):
        found = _net_reading(box.text)
        if found is not None:
            match, amount = found
            return box, match, amount
    return None


_ORIGIN_RE = re.compile(
    r"(?:PRODUCT|PRODUCE|PRODUCED|MADE|BREWED|DISTILLED|BOTTLED|IMPORTED)\s+"
    r"(?:OF|IN|FROM)\s+(?:THE\s+)?"
    r"([A-Za-z][\w.]*(?:\s+(?:AND\s+|OF\s+)?[A-Za-z][\w.]*){0,3})",
    re.I,
)

# The same words that state a country state a State: a label reading
# "DISTILLED IN INDIANA" is not declaring a country of origin. A place on this
# list is not reported as one.
_US_STATES = frozenset(
    "ALABAMA ALASKA ARIZONA ARKANSAS CALIFORNIA COLORADO CONNECTICUT DELAWARE "
    "FLORIDA GEORGIA HAWAII IDAHO ILLINOIS INDIANA IOWA KANSAS KENTUCKY "
    "LOUISIANA MAINE MARYLAND MASSACHUSETTS MICHIGAN MINNESOTA MISSISSIPPI "
    "MISSOURI MONTANA NEBRASKA NEVADA OHIO OKLAHOMA OREGON PENNSYLVANIA "
    "TENNESSEE TEXAS UTAH VERMONT VIRGINIA WASHINGTON WISCONSIN WYOMING".split()
) | frozenset({
    "NEW HAMPSHIRE", "NEW JERSEY", "NEW MEXICO", "NEW YORK", "NORTH CAROLINA",
    "NORTH DAKOTA", "RHODE ISLAND", "SOUTH CAROLINA", "SOUTH DAKOTA",
    "WEST VIRGINIA", "DISTRICT OF COLUMBIA", "PUERTO RICO",
})
_NAME_LEAD_IN_RE = re.compile(
    r"\b(?:BOTTLED|PRODUCED|DISTILLED|IMPORTED|BREWED|PACKED|VINTED|BLENDED|"
    r"MANUFACTURED|CANNED)(?:\s+AND\s+\w+)?\s+(?:BY|FOR)\b[:\s]*",
    re.I,
)
_CITY_STATE_RE = re.compile(r"([A-Z][A-Za-z.\- ]{2,}),\s*([A-Z]{2})\b")

# Plain OCR returns lines, not labelled fields, so the class/type line is
# found by the designations that can appear on it. This is a lexicon for
# spotting the line, not a list of what is allowed: which designations the
# application and the regulations accept is the rule pack's to say.
_CLASS_WORDS = (
    "WHISKEY", "WHISKY", "BOURBON", "RYE", "SCOTCH", "VODKA", "GIN", "RUM",
    "TEQUILA", "MEZCAL", "BRANDY", "COGNAC", "LIQUEUR", "CORDIAL", "SCHNAPPS",
    "ABSINTHE", "GRAPPA", "AQUAVIT", "SOJU", "SAKE", "WINE", "CHAMPAGNE",
    "PROSECCO", "SPARKLING", "CHARDONNAY", "MERLOT", "CABERNET", "SAUVIGNON",
    "PINOT", "RIESLING", "ZINFANDEL", "SANGIOVESE", "SYRAH", "SHIRAZ",
    "MALBEC", "TEMPRANILLO", "MOSCATO", "ROSE", "PORT", "SHERRY", "VERMOUTH",
    "CIDER", "MEAD", "BEER", "ALE", "LAGER", "STOUT", "PORTER", "PILSNER",
    "IPA", "MALT BEVERAGE", "SAISON", "BOCK", "HEFEWEIZEN",
)

# The lexicon reduced to words once, at import, in the same reduction the rule
# pack compares designations in.
_CLASS_PHRASES = tuple(normalize_words(word) for word in _CLASS_WORDS)


def _names_a_designation(text: str) -> bool:
    """Does this line carry a class or type designation?

    **Whole words, not letters.** The test used to be a substring search over
    the folded line, so `DISTILLED IN VIRGINIA` named a gin, `IMPORTED BY` and
    `PORTLAND, OR` named a port, `WHOLESALE` named an ale and `MUNICIPAL` named
    an IPA. `_largest_matching` then took the tallest line that matched, and a
    lead-in or a city is often set larger than the designation itself — so the
    reader reported an importer's address as the label's class and type.

    The reduction is `app.rules._validators._helpers`, which is what the rule
    pack compares designations in and where "gin must not match inside
    Virginia" is already written down. Multi-word designations keep working:
    `MALT BEVERAGE` and `INDIA PALE ALE` are matched as consecutive words.

    This is still a lexicon for *spotting* the line, not a list of what is
    allowed. Which designations the application and the regulations accept is
    the rule pack's to say, and its `recognised_classes` lists are deliberately
    narrower than this one: a label printing CHARDONNAY carries a class/type
    line whether or not any pack recognises the word.
    """
    if _NAME_LEAD_IN_RE.search(text):
        # A name-and-address line names a designation often enough to win on
        # height and never is one: `IMPORTED BY WINE WINE SITUATION LLC` opens
        # with the lead-in that says what it is. The words after "bottled by" or
        # "imported by" are a business, and its trade name may be anything.
        return False
    words = normalize_words(text)
    return any(word_run_present(words, phrase) for phrase in _CLASS_PHRASES)


def _mean_score(boxes: list[_Box]) -> float:
    scores = [b.score for b in boxes if b.score > 0]
    return sum(scores) / len(scores) if scores else 0.0


def _confidence(field: str, boxes: list[_Box], *, factor: float = 1.0) -> float:
    if not boxes:
        return 0.0
    value = _mean_score(boxes) * _PICK_CERTAINTY[field] * factor
    return max(0.0, min(1.0, value))


def _parse(
    *,
    boxes: list[_Box],
    warning_boxes: list[_Box],
    rotation: int,
    heading_measurement: HeadingMeasurement | None = None,
) -> dict[str, tuple[dict, tuple[int, int, int, int] | None, str | None]]:
    """Every field's payload, its box and the text it was read from.

    Pure: it reads the boxes and nothing else. `heading_measurement` is the one
    reading that needs the image itself, and `_read` takes it before calling
    here, so a reading frozen as boxes can be re-parsed with no image at all.
    """
    out: dict[str, tuple[dict, tuple[int, int, int, int] | None, str | None]] = {}

    # -- the government warning ------------------------------------------
    block = _warning_block(warning_boxes)
    if block is None:
        out["gov_warning"] = (
            {
                "text": "", "heading_text": "", "heading_all_caps": False,
                "heading_bold": False, "type_size_pt": 0.0, "confidence": 0.0,
            },
            None,
            None,
        )
    else:
        text, heading_text, heading_box, block_boxes = block
        letters = [c for c in heading_text if c.isalpha()]
        measurement = heading_measurement or HeadingMeasurement(
            False, 0.0, 0.0, 0.0, confident=False
        )
        factor = _ROTATED_FRAME_PENALTY if rotation else 1.0
        payload = {
            "text": text,
            "heading_text": heading_text,
            "heading_all_caps": bool(letters) and all(c.isupper() for c in letters),
            # The reader reports no type size: a photograph does not carry the
            # scale that would turn pixels into points. Decision 0006 puts the
            # rules that need one out of scope.
            "type_size_pt": 0.0,
            "confidence": _confidence("gov_warning", block_boxes, factor=factor),
            "heading_bold_measured": measurement.is_bold,
            "heading_bold_measured_confident": measurement.confident,
            "heading_bold_width_height_ratio": measurement.width_height_ratio,
        }
        # A boldness that could not be measured is absent, not false. Writing
        # `False` here stated a measurement nobody took: a heading the reader
        # could not measure was recorded as *not bold*, which is a claim about
        # the label rather than about the reading. It also put the two readers
        # at odds — `app/vision/cloud.py` leaves the key alone on an unconfident
        # measurement — over the same signal. Absent is what both now mean by
        # "not measured", and `heading_bold_measured_confident` is how a rule
        # asks.
        if measurement.confident:
            payload["heading_bold"] = measurement.is_bold
        out["gov_warning"] = (payload, heading_box.as_bbox(), text)

    warning_texts = {b.text for b in (block[3] if block else [])}
    body = [b for b in boxes if b.text not in warning_texts]
    joined = " ".join(b.text for b in _reading_order(body))

    # -- alcohol content --------------------------------------------------
    abv_box, abv_match = _first_match(body, _ABV_RE)
    if abv_match:
        raw = next(g for g in abv_match.groups() if g)
        # The label's own wording, alongside the number rather than instead of
        # it. Keeping only the number left the format check comparing the rule
        # pack's regex against a sentence the validator had written itself, so
        # it passed every label it was shown and rejected every label it was
        # shown nothing about (`docs/decisions.md#0011`). The rule packs already
        # name the key they want for this: `evidence_required: [alc_text]`.
        alc_text = _alcohol_statement(abv_box.text, raw) or abv_match.group(0).strip()
        out["abv"] = (
            {
                "abv_pct": float(raw.replace(",", ".")),
                "unit": "%",
                "alc_text": alc_text,
                "confidence": _confidence("abv", [abv_box]),
            },
            abv_box.as_bbox(),
            alc_text,
        )
    else:
        out["abv"] = (
            {"abv_pct": None, "unit": "", "alc_text": "", "confidence": 0.0}, None, None
        )

    # -- net contents -----------------------------------------------------
    net = _net_contents(body)
    net_box = net[0] if net is not None else None
    if net is not None:
        _, net_match, net_amount = net
        out["net_contents"] = (
            {
                "net_contents_value": net_amount,
                # As the label prints it. The reader used to upper-case it and
                # strip its dots and spaces, which was a fourth spelling of the
                # same reduction: everything downstream — the rule pack's
                # `quantity_match`, the application form, the accuracy harness —
                # already reduces a unit through `app.rules.units.unit_key`
                # before it converts, and `FL. OUNCES` is what a reviewer reading
                # the envelope should see the label said.
                "unit": net_match.group(2).strip(),
                "confidence": _confidence("net_contents", [net_box]),
            },
            net_box.as_bbox(),
            net_match.group(0).strip(),
        )
    else:
        out["net_contents"] = (
            {"net_contents_value": None, "unit": "", "confidence": 0.0}, None, None
        )

    # -- country of origin ------------------------------------------------
    origin_box, origin_match = _first_match(body, _ORIGIN_RE, reject=_names_a_state)
    if origin_match:
        # Reported as the label writes it, not tidied: what the label says is
        # the evidence, and the rule pack settles whether it agrees with the
        # application.
        out["country_origin"] = (
            {
                "country": origin_match.group(1).strip(" .,"),
                "confidence": _confidence("country_origin", [origin_box]),
            },
            origin_box.as_bbox(),
            origin_match.group(0).strip(),
        )
    else:
        # Emitted empty rather than left out: a missing observation makes the
        # origin rule skip without saying so.
        out["country_origin"] = ({"country": "", "confidence": 0.0}, None, None)

    # -- class and type ---------------------------------------------------
    class_box = _largest_matching(body, _names_a_designation)
    if class_box is not None:
        out["class_type"] = (
            {
                "class_type": class_box.text.strip(),
                "confidence": _confidence("class_type", [class_box]),
            },
            class_box.as_bbox(),
            class_box.text.strip(),
        )
    else:
        out["class_type"] = ({"class_type": "", "confidence": 0.0}, None, None)

    # -- brand ------------------------------------------------------------
    # The brand is the name the label is built around, and on a label it is
    # set larger than anything else. The lines that carry another mandatory
    # element are taken out first, so a large alcohol statement or class
    # designation is not read as the brand.
    taken = {
        b.text for b in (abv_box, net_box, origin_box, class_box) if b is not None
    } | warning_texts
    brand_box = _largest_matching(
        body,
        lambda t: (
            t.strip() not in taken
            and any(c.isalpha() for c in t)
            and not _BARCODE_RE.match(t.strip())
            and len(t.strip()) > 2
        ),
    )
    if brand_box is not None:
        out["brand_name"] = (
            {
                "brand_name": brand_box.text.strip(),
                "confidence": _confidence("brand_name", [brand_box]),
            },
            brand_box.as_bbox(),
            brand_box.text.strip(),
        )
    else:
        out["brand_name"] = ({"brand_name": "", "confidence": 0.0}, None, None)

    # -- name and address -------------------------------------------------
    out["name_address"] = _name_address(body, joined)
    return out


def _alcohol_statement(text: str, figure: str) -> str:
    """The alcohol statement inside one box's text, as printed.

    A box often carries more than the statement — `40% ALC. BY VOL-700 mL` is
    one box on a real label, and so is `12% ALC. BY VOL. | CONTAINS SULFITES`.
    The candidate taken is the first that carries the figure the percentage was
    parsed from, so a net-contents number earlier in the same box cannot be
    returned as the alcohol statement.
    """
    for candidate in _ALC_STATEMENT_RE.finditer(text):
        if figure in candidate.group(0):
            return candidate.group(0).strip()
    return ""


def _names_a_state(match: re.Match) -> bool:
    return _fold(match.group(1)).strip(" .,") in _US_STATES


def _first_match(boxes: list[_Box], pattern: re.Pattern, *, reject=None):
    """The first box whose text the pattern matches, and the match.

    `reject` discards a match that the pattern found but that does not mean
    what the field means, and the search carries on past it.
    """
    for box in _reading_order(boxes):
        for match in pattern.finditer(box.text):
            if reject is not None and reject(match):
                continue
            return box, match
    return None, None


def _largest_matching(boxes: list[_Box], predicate) -> _Box | None:
    """The tallest box whose text satisfies `predicate`.

    Type size is what a label uses to say which words matter most, so the
    tallest line is the best reading of a field plain OCR does not label.
    """
    candidates = [b for b in boxes if b.text.strip() and predicate(b.text)]
    if not candidates:
        return None
    return max(candidates, key=lambda b: b.height)


def _name_address(boxes: list[_Box], joined: str):
    """The applicant's name and address, found by the words in front of it.

    A label prints the block behind a lead-in — "BOTTLED BY", "IMPORTED BY" —
    and follows the name with a city and a State. Both are looked for; what is
    found is reported and what is not is left empty.
    """
    empty = ({"name": "", "city": "", "state": "", "confidence": 0.0}, None, None)
    ordered = _reading_order(boxes)
    for index, box in enumerate(ordered):
        lead_in = _NAME_LEAD_IN_RE.search(box.text)
        if not lead_in:
            continue
        # The name may finish the lead-in's own line or begin the next.
        tail = box.text[lead_in.end():].strip(" ,.:;")
        following = ordered[index + 1: index + 4]
        parts = [tail] + [b.text.strip() for b in following]
        used = [box] + following
        name = next((p for p in parts if p and not _CITY_STATE_RE.search(p)), "")
        city, state = "", ""
        for part in parts:
            place = _CITY_STATE_RE.search(part)
            if place:
                city, state = place.group(1).strip(), place.group(2)
                break
        if not (name or city):
            continue
        return (
            {
                "name": name,
                "city": city,
                "state": state,
                "confidence": _confidence("name_address", used),
            },
            box.as_bbox(),
            " ".join(p for p in (name, city, state) if p),
        )

    # No lead-in anywhere. A city and a State on their own still place the
    # bottler, so they are reported without a name.
    place = _CITY_STATE_RE.search(joined)
    if place:
        return (
            {
                "name": "",
                "city": place.group(1).strip(),
                "state": place.group(2),
                # Nothing tied this place to the applicant, so the reading is
                # reported at half the certainty a lead-in would have given it.
                "confidence": _confidence("name_address", boxes, factor=0.5),
            },
            None,
            place.group(0),
        )
    return empty
