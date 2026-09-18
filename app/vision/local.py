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
import statistics
import threading
import time
import unicodedata
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from importlib import metadata
from io import BytesIO
from itertools import pairwise
from typing import Any, Protocol, cast

import numpy as np
from PIL import Image

from app.config import Settings
from app.rules._validators._helpers import normalize_words, word_run_present
from app.rules.units import UnitTable, millilitres, millilitres_from_text, shipped_table
from app.schemas.calls import CallRecord
from app.schemas.expected import BeverageClass
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.label import Face, Label
from app.vision import quality
from app.vision.faces import QUALITY_FIELD_ID, is_unreadable, merge_readings
from app.vision.heading_measure import HeadingMeasurement, measure_heading_bold_image

_logger = logging.getLogger("app.vision.local")


# The longest edge any image is scaled down to before reading. Label
# photographs from the registry run to several thousand pixels, and the
# detection model gains nothing above this while costing time on every one.
MAX_EDGE_PX = 1600

# How sure rapidocr's 0/180 line classifier must be before a line is read
# upside down. Its default, 0.9, flips upright lines of the health warning on
# real labels, and a flipped line reads as noise: `ttb-26218001000369` came back
# 131 characters from the §16.21 text at 0.9 and exact at 0.999. At 0.999 no
# field on the 38-label corpus reads worse into a rejection
# (`docs/decisions.md#0039`).
LINE_FLIP_CONFIDENCE = 0.999

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

# A brand mark is routinely set over several lines, and the engine returns one
# box per line. These say which neighbouring lines are part of the same mark:
# a line set below a third of the tallest line's height is subordinate text
# rather than part of the name, and a line further away than these fractions of
# that height is a different block of the label. They are ratios rather than
# pixel counts because they are read off a thumbnail whose scale varies.
_BLOCK_MIN_HEIGHT_RATIO = 0.30
_BLOCK_MAX_VERTICAL_GAP = 0.40
_BLOCK_MAX_HORIZONTAL_GAP = 0.50

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
    def type_size(self) -> float:
        """How large this line's type is set, whichever way the line runs.

        A line of text is long in the direction it reads and short across it,
        so the shorter side is the type's size and the longer one is how much
        of it there is. Height alone says the same thing only while the line is
        horizontal: a warning printed up the side of a label comes back as a
        497x55 box, and read as height it is the largest type on the label by a
        factor of five. It is not — it is 55pt type in a tall thin box.
        """
        return min(self.height, self.width)

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
        "heading_measurement": None
        if measurement is None
        else {
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
        heading_measurement=None
        if measurement is None
        else HeadingMeasurement(
            is_bold=measurement["is_bold"],
            mean_stroke_width=measurement["mean_stroke_width"],
            mean_character_height=measurement["mean_character_height"],
            width_height_ratio=measurement["width_height_ratio"],
            confident=measurement["confident"],
        ),
        frame_size=tuple(data["frame_size"]),
    )


@lru_cache(maxsize=1)
def _warm_image_bytes() -> bytes:
    """The image the warm read runs on, drawn once and kept.

    Dark text on white, large enough and with enough space around it that the
    detector finds a box and hands the recognizer something to read. It is
    never scored, never parsed and never reaches a rule; it exists so that the
    three models run once before a label arrives.
    """
    image = Image.new("RGB", (640, 220), "white")
    from PIL import ImageDraw, ImageFont

    try:
        font = ImageFont.load_default(40)
    except TypeError:  # pragma: no cover — older PIL, one fixed size only
        font = ImageFont.load_default()
    ImageDraw.Draw(image).text((24, 80), "WARM 750 ML 40% ALC/VOL", fill="black", font=font)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def parse_reading(reading: _Reading) -> dict[str, dict]:
    """The seven field payloads a reading produces, keyed by field.

    The production path itself, minus the pixels: `extract` reports exactly
    these payloads. It is what the replay suite drives and what scores a frozen
    recording.
    """
    return {
        field: payload
        for field, (payload, _bbox, _text) in _parse(
            boxes=reading.boxes,
            warning_boxes=reading.warning_boxes,
            rotation=reading.rotation,
            heading_measurement=reading.heading_measurement,
        ).items()
    }


def _fold(text: str) -> str:
    """One string reduced for matching only: accents dropped, case folded.

    Used to find a phrase, never to report one. What is reported is always the
    text the engine returned.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).upper()


_HEADING_RE = re.compile(r"GOVERNMENT\s*WARNING", re.I)

# How much of the narrower span two boxes must share before they count as the
# same column of text, and how many heading-heights tall a box may be before it
# stops being a line of running text. Both are in `_warning_block`, which says
# what they separate and why.
_WARNING_COLUMN_OVERLAP_MIN = 0.5
_WARNING_LINE_HEIGHT_MAX = 2.5
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


class _OcrResult(Protocol):
    """What this module reads off one RapidOCR call."""

    txts: Sequence[object] | None
    scores: Sequence[float] | None
    boxes: Any


class _OcrEngine(Protocol):
    """The whole of RapidOCR this module uses.

    RapidOCR's own `__call__` is annotated as returning one of four output
    types, one per combination of the three stage flags. This module asks for
    two of them: a full pass over an image, and recognition alone over a strip
    already located (`_read_strip`). Both carry text, so `_load` casts to this
    and the cast is where that claim is written down.

    The flags are passed on every call, never left to default, because
    `RapidOCR.__call__` begins with `update_params` and those settings persist
    on the engine afterwards. One recognition-only call would otherwise leave
    the shared engine detecting nothing on the next label — and the next label
    belongs to a different request.
    """

    def __call__(
        self,
        image: Any,
        use_det: bool | None = None,
        use_cls: bool | None = None,
        use_rec: bool | None = None,
    ) -> _OcrResult | None: ...


class LocalVisionExtractor:
    """Reads one label image with a CPU OCR engine and reports seven fields."""

    @property
    def reader_version(self) -> str:
        """`local:rapidocr@<installed version>`, for the audit trail.

        Read from the installed package rather than written here, the way
        `Settings.app_version` is, so upgrading the engine changes what the
        record says without anyone remembering to edit a constant. A constant
        would go stale silently, and a stale reader version in a compliance
        record is worse than none: it names the wrong reader with confidence.

        `"unknown"` where the metadata is missing, which is the same answer
        `app_version` gives — a version this cannot establish is one it must
        not state.
        """
        try:
            return f"local:rapidocr@{metadata.version('rapidocr')}"
        except metadata.PackageNotFoundError:
            return "local:rapidocr@unknown"

    def __init__(self, *, settings: Settings, ring_buffer: deque) -> None:
        self._settings = settings
        self._ring = ring_buffer
        self._engine: _OcrEngine | None = None
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

    def _load(self) -> _OcrEngine:
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
                "Cls.cls_thresh": LINE_FLIP_CONFIDENCE,
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
        return cast("_OcrEngine", engine)

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

    async def warm(self) -> None:
        """Load the models, then read one image, so no label pays for either.

        ``ensure_loaded`` builds the onnxruntime sessions; it does not run
        them. Each graph is optimized and its memory arenas allocated on the
        first inference, and that cost lands on whoever submits first: measured
        in a fresh process here, the first read after a load took 0.48s against
        0.35s for the two after it, and running one read first brought it to
        0.37s. On the deployed service, where every read is several times
        slower, the same gap is over a second, and the service scales to zero,
        so a reviewer's first click is what pays it.

        The image is generated rather than shipped — a real label kept as a
        warm-up fixture is a second thing to keep true — and what it says does
        not matter, because the point is to run the graphs rather than to read
        anything. It does have to carry text the detector finds: a warm read
        that detects nothing never reaches the recognition model, which is the
        larger of the three, and leaves most of the cost still to pay.

        Failure is logged, not raised. A warm that did not happen costs the
        first label what it used to cost; a warm that takes the process down
        costs everything. Readiness is ``ensure_loaded``'s question, and it is
        awaited above, so a caller that needs an answer still gets one.
        """
        await self.ensure_loaded()
        try:
            await asyncio.to_thread(self._read_serialised, _warm_image_bytes())
        except Exception:
            _logger.warning(
                "reader_warm_read_failed",
                extra={"reason_code": "ENGINE.OK.NONE"},
                exc_info=True,
            )

    # -- reading -----------------------------------------------------------

    def _boxes(self, image: Image.Image) -> list[_Box]:
        engine = self._engine
        if engine is None:
            raise RuntimeError("the reader was asked for boxes before its models were loaded")
        result = engine(np.array(image), use_det=True, use_cls=True, use_rec=True)
        if result is None or result.txts is None:
            return []
        scores = result.scores if result.scores is not None else [1.0] * len(result.txts)
        boxes: list[_Box] = []
        for quad, text, score in zip(result.boxes.tolist(), result.txts, scores, strict=True):
            xs = [p[0] for p in quad]
            ys = [p[1] for p in quad]
            boxes.append(
                _Box(
                    x0=min(xs),
                    x1=max(xs),
                    y0=min(ys),
                    y1=max(ys),
                    text=str(text),
                    score=float(score),
                )
            )
        return boxes

    def _read_strip(self, image: Image.Image, box: _Box) -> str | None:
        """What one sideways strip says, read without a second detector pass.

        The upright pass has already found this box and reported where it sits.
        Turning that crop upright and asking the engine for recognition alone
        skips the expensive half of a pass — `use_det=False` — so a strip costs
        about 10 ms rather than the 440 ms a rotated frame costs.

        Only 90° is tried, not both ways. rapidocr runs a 0/180 orientation
        classifier over each crop before recognising it, so a strip printed the
        other way up comes back the right way round from the same call:
        measured on ttb-26212001000085, the strips read the same words at 90°
        and at 270° (`docs/decisions.md#0036`).

        `None` means the strip could not be read — no engine loaded, or nothing
        recognised. Both are "this strip cannot rule the warning out", which is
        the answer the caller acts on.
        """
        engine = self._engine
        if engine is None:
            return None
        crop = image.crop(
            (
                max(0, int(box.x0) - _SCREEN_PAD_PX),
                max(0, int(box.y0) - _SCREEN_PAD_PX),
                min(image.size[0], int(box.x1) + _SCREEN_PAD_PX),
                min(image.size[1], int(box.y1) + _SCREEN_PAD_PX),
            )
        ).rotate(90, expand=True)
        result = engine(np.array(crop), use_det=False, use_cls=True, use_rec=True)
        if result is None or not result.txts:
            return None
        return str(result.txts[0])

    def _sideways_may_be_the_warning(self, image: Image.Image, boxes: list[_Box]) -> bool:
        """Whether the sideways text on this label could be the warning.

        Asked after `_has_sideways_text` has said there is sideways text, and
        before the two rotated passes that would read the whole label again to
        find out what it is. The strips are read in place instead, and a strip
        carrying any of the warning's own words sends the re-read ahead.

        It answers yes wherever it cannot answer no — no strips to read, or a
        strip that came back empty. The cost of a wrong yes is the two passes
        that used to run anyway; the cost of a wrong no is a government warning
        the label never got checked for, so the two are not weighed evenly.
        """
        strips = [b for b in boxes if b.height / max(1e-6, b.width) >= _SCREEN_TALL_RATIO]
        if not strips:
            return True
        for box in strips:
            text = self._read_strip(image, box)
            if text is None:
                return True
            if _WARNING_SCREEN_WORDS.intersection(normalize_words(text)):
                return True
        return False

    async def extract(self, label: Label) -> list[FieldObservation]:
        """Read every face of the label and return one reading of it.

        A face the quality gate refuses stops the label: it is a photograph
        nobody can check, and on a two-face label it is as likely to be the
        one carrying the government warning as the one carrying the brand.
        """
        readings: list[list[FieldObservation]] = []
        for face in label.faces:
            reading = await self._extract_face(label, face)
            if is_unreadable(reading):
                return reading
            readings.append(reading)
        return merge_readings(readings)

    async def _extract_face(self, label: Label, face: Face) -> list[FieldObservation]:
        report = quality.assess(face)
        if report.disposition != "ok":
            return [
                FieldObservation(
                    field_id=QUALITY_FIELD_ID,
                    beverage_class=BeverageClass.SPIRITS,
                    observed_value=None,
                    evidence=(
                        Evidence(
                            field_id=QUALITY_FIELD_ID,
                            source=EvidenceSource.DERIVED,
                            panel=face.face_tag,
                            bbox=None,
                            extracted_text=report.reason_code,
                            match_kind=MatchKind.NONE,
                            confidence=0.0,
                        ),
                    ),
                    upstream_meta={
                        "disposition": report.disposition,
                        "reason_code": report.reason_code,
                        "face_tag": face.face_tag,
                    },
                )
            ]

        await self.ensure_loaded()
        t0 = time.monotonic()
        payloads, meta = await asyncio.to_thread(self._read_serialised, face.image_bytes)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        self._record(label=label, face=face, payloads=payloads, meta=meta, elapsed_ms=elapsed_ms)

        # The legibility gate that means anything, and the only one that can be
        # applied honestly: the detector found no text on this image, at any of
        # the three rotations it tries, so there is nothing on it for any rule
        # to check. Whatever made it unreadable - glare, a thumb over the lens,
        # a blank page - the answer to the person who sent it is the same, and
        # it does not depend on guessing the cause from the pixels. The gates in
        # `app/vision/quality.py` run before the read and cannot see this.
        if not meta.get("boxes_found"):
            return [
                FieldObservation(
                    field_id=QUALITY_FIELD_ID,
                    beverage_class=BeverageClass.SPIRITS,
                    observed_value=None,
                    evidence=(
                        Evidence(
                            field_id=QUALITY_FIELD_ID,
                            source=EvidenceSource.DERIVED,
                            panel=face.face_tag,
                            bbox=None,
                            extracted_text="WARNING.LEGIBILITY.LOW_RESOLUTION",
                            match_kind=MatchKind.NONE,
                            confidence=0.0,
                        ),
                    ),
                    upstream_meta={
                        "disposition": "needs_better_photo",
                        "reason_code": "WARNING.LEGIBILITY.LOW_RESOLUTION",
                        "face_tag": face.face_tag,
                        **meta,
                    },
                )
            ]

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
                            panel=face.face_tag,
                            bbox=bbox,
                            extracted_text=text,
                            match_kind=MatchKind.NONE,
                            confidence=float(payload.get("confidence", 0.0)),
                        ),
                    ),
                    upstream_meta={"bbox": bbox, "face_tag": face.face_tag, **meta},
                )
            )
        return observations

    def _record(
        self, *, label: Label, face: Face, payloads: dict, meta: dict, elapsed_ms: int
    ) -> None:
        readable = {k: v[0] for k, v in payloads.items()}
        self._ring.append(
            CallRecord(
                ts=datetime.now(UTC),
                batch_id=label.batch_id,
                label_id=label.label_id,
                stage="vision.local_ocr",
                request={"call_kind": "local_ocr", "image_size": len(face.image_bytes)},
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

        # A label photographed on its side reads as nothing at all, and some
        # upright labels carry the warning printed sideways up an edge. Where no
        # warning heading is found, the image is tried on its side both ways,
        # and the frame that finds one is the frame the warning is read from.
        #
        # Those two extra passes are only ever spent on the warning: the other
        # six fields are read from `boxes`, the upright pass, whatever the
        # rotated frames turn up. So two questions are asked before paying for
        # them — is there sideways text here at all (`_has_sideways_text`), and
        # does it read like the warning (`_sideways_may_be_the_warning`). The
        # first reads box shapes and costs nothing; the second reads the strips
        # themselves for about 10 ms each, against 440 ms for one rotated pass.
        warning_boxes = boxes
        rotation = 0
        warning_image = image
        found = _find_heading(boxes)
        if found is None:
            # A label with no upright heading may still not get a second look:
            # either its boxes are not sideways at all, or the strips do not
            # read like the warning. Either way the label is reported as
            # carrying no warning, and since the confidence-floor fix that is a
            # §16.21 rejection rather than a reviewer's question - so the
            # decision not to look again is recorded rather than left silent.
            #
            # It goes to the log and not to the envelope on purpose.
            # `output_hash` is taken over the whole envelope
            # (`app/services/audit.py`), so a field here would move every stored
            # hash and every frozen replay recording. The README names this gap
            # under `## Limitations` for the reader who is not reading logs.
            sideways = _has_sideways_text(boxes)
            if sideways and self._sideways_may_be_the_warning(image, boxes):
                for angle in (90, 270):
                    rotated = image.rotate(angle, expand=True)
                    candidate = self._boxes(rotated)
                    candidate_heading = _find_heading(candidate)
                    if candidate_heading is not None:
                        warning_boxes, rotation, warning_image = candidate, angle, rotated
                        found = candidate_heading
                        break
            else:
                # `has_sideways_text` tells the two apart on its own: false
                # means the box shapes declined, true means the strips did.
                _logger.info(
                    "sideways_reread_declined",
                    extra={"has_sideways_text": sideways, "box_count": len(boxes)},
                )

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


# The shape of a detected box separates text the reader can already read from
# text lying on its side. Upright text detects as boxes wider than they are
# tall; sideways text detects as tall narrow strips, either several of them or
# one long one.
#
# Measured over the corpus's 62 images on 2026-09-17 by `eval.box_ratios`,
# which re-derives every number below. The gate is consulted only where the
# upright pass found no warning heading, so 34 of those images never reach it
# and these thresholds answer for the other 28:
#
#   * The one label whose warning is printed sideways up its edge
#     (26212001000085, front) has a tallest box of 9.04 and five boxes at or
#     past 2.0, so `_SIDEWAYS_RATIO` and `_SIDEWAYS_MIN_BOXES` catch it twice
#     over.
#   * Of the 28, four are sent for the re-read and 24 are spared it. The
#     tallest box among the spared is 2.8, and no spared image has either two
#     boxes past 2.0 or one past `_SIDEWAYS_LONE_RATIO`. The gap between what
#     fires and what does not is a clear one here: nothing spared comes within
#     1.2 of the lowest box that fires.
#   * `_SIDEWAYS_LONE_RATIO` is what catches the two images whose single tall
#     strip sits at 5.0 and 4.05. Neither carries a warning, so on this corpus
#     that rule buys only re-reads that find nothing.
#
# What the corpus cannot settle, and the numbers above should not be read as
# settling: it holds exactly one label with a sideways-printed warning. These
# thresholds separate that one example cleanly, which is not the same as
# knowing they generalise, and three of the four images that fire are already
# false positives. Erring that way is deliberate — see `_has_sideways_text`.
_SIDEWAYS_RATIO = 2.0
_SIDEWAYS_MIN_BOXES = 2
_SIDEWAYS_LONE_RATIO = 3.0

# The screen that stands between the gate above and the two full passes below.
#
# The gate reads box shapes, which say that a frame holds sideways text but not
# what it says, so it fires on any label with a strip of vertical type — a
# barcode, a net-contents line up an edge, a vertical brand mark. Reading those
# strips settles it: recognition alone over the boxes the upright pass already
# found costs about 10 ms a strip, against about 440 ms for one rotated pass,
# because it skips detection entirely and recognises only text already located.
#
# Measured over all 62 corpus images, 2026-09-17
# (`docs/decisions.md#0036`): four
# images reach this point, and the rotated re-read recovers a warning from one
# of them, ttb-26212001000085. Its strips read "THE SURGEON" and "DRIVE ACAR
# OROPERATEMACHINERY,ANDM"; the three the re-read finds nothing on read
# "3105540651", "750 ML" and an Italian brand line. So the screen keeps the
# re-read where it pays and drops about 875 ms from each of the other three.
#
# `_SCREEN_TALL_RATIO` is looser than `_SIDEWAYS_RATIO` on purpose: every strip
# the gate could have fired on is read, and some besides. A strip more costs
# 10 ms; a strip missed is a warning missed.
_SCREEN_TALL_RATIO = 1.5
_SCREEN_PAD_PX = 4

# The §16.21 warning's own content words, which is what the screen asks each
# strip for. Function words are left out — "the" on a label says nothing — and
# so is anything the warning shares with ordinary label copy.
#
# This is the reader deciding where to look, never what the label says: a word
# here that drifts from the statutory text can cost a re-read, and cannot
# change a verdict. `assets/warnings/govt_warning_16_21.txt` is the text these
# come from, and `tests/test_vision_warning_screen.py` holds them to it rather
# than a comment promising they match.
_WARNING_SCREEN_WORDS = frozenset(
    {
        "government",
        "warning",
        "according",
        "surgeon",
        "general",
        "women",
        "drink",
        "alcoholic",
        "beverages",
        "pregnancy",
        "birth",
        "defects",
        "consumption",
        "impairs",
        "ability",
        "drive",
        "operate",
        "machinery",
        "health",
        "problems",
    }
)


def _has_sideways_text(boxes: list[_Box]) -> bool:
    """Whether this frame holds text that only a rotated read would recover.

    The rotated re-read costs a full detector pass per angle and produces
    nothing but the warning, so it is worth running only where there is
    sideways text to find. Asking the boxes settles it without another pass:
    the detector reports where it found text and how that text is shaped, and
    sideways text is tall where upright text is wide.

    Two shapes count, because sideways text arrives as either. A block of it
    splits into several tall strips, so two boxes past `_SIDEWAYS_RATIO` is
    enough; a single line of it comes back as one very tall strip that nothing
    else matches, so one box past `_SIDEWAYS_LONE_RATIO` is enough on its own.
    Over the corpus this keeps the re-read on the one label whose warning is
    printed up its edge, and spares it 24 of the 28 images that reach this gate
    at all — the other 34 find their heading upright and never ask.

    Erring toward running it is deliberate: a re-read that finds nothing costs
    time, and a warning missed because no re-read ran is a compliance finding
    the label never got.
    """
    ratios = [(box.y1 - box.y0) / max(1e-6, box.x1 - box.x0) for box in boxes]
    if sum(1 for r in ratios if r >= _SIDEWAYS_RATIO) >= _SIDEWAYS_MIN_BOXES:
        return True
    return any(r >= _SIDEWAYS_LONE_RATIO for r in ratios)


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
        covered[int(b.x0 - left) : int(b.x1 - left) + 1] = True
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
    for lo, hi in pairwise(cuts):
        column = [b for b in boxes if lo <= (b.x0 + b.x1) / 2.0 < hi]
        if column:
            columns.append(column)
    return columns or [boxes]


def _reading_order(boxes: list[_Box]) -> list[_Box]:
    """Boxes in the order a person reads them: column by column, row by row.

    Rows are cut at multiples of how tall a line is on this label, and that is
    the *typical* box, not the tallest one. A label carries boxes that are not
    lines of text — a stylised brand, a logotype, a word set sideways — and
    taking the tallest made one of them redefine where every row on the label
    began. Measured: returning a 92-pixel `WhitServe` logotype to the body of
    an imported wine, where the lines are around 50 pixels, moved the row
    boundary far enough that `IMPORTED BY:` and `PRODUCED BY:` swapped places
    and the reader named the Italian producer as the applicant instead of the
    Connecticut importer. The median is what "a line on this label" means.
    """
    ordered: list[_Box] = []
    for column in _columns(boxes):
        heights = [b.height for b in column if b.height]
        line_height = statistics.median(heights) if heights else 1.0
        ordered.extend(sorted(column, key=lambda b: (round(b.y0 / (line_height * 0.7)), b.x0)))
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
        b
        for b in boxes
        if b.y1 >= heading.y0 - line_height * 0.6 and not _BARCODE_RE.match(b.text.strip())
    ]

    # The statement is a block of text, so it occupies a column and its lines
    # are lines. Taking everything at the heading's height instead took a band
    # across the whole label, and a back label prints other things in that
    # band: a keg's tapping instructions in the next column over, a state
    # deposit line, an importer's web address. `common.warning.verbatim`
    # compares the whole statement, so one neighbour's box rejected a warning
    # the label prints correctly — 24 of the 37 labels in the manifest, before
    # this, a sweep of the manifest reported in commit `8ca3ecc`.
    #
    # Two tests, both of them what a person means by "the block of text under
    # that heading":
    #
    # - **Its own column.** The span starts at the heading's and grows with
    #   each line kept, because a heading is often narrower than the lines
    #   beneath it. A box from the next column over overlaps that span by
    #   nothing at all, so half the narrower of the two spans separates them
    #   with room to spare.
    # - **Its own line height.** A rotated label reads back as tall vertical
    #   boxes — a cognac front returns `Cognac XO` 311 pixels tall against a
    #   47-pixel heading — and a box that tall is not a line of running text.
    #   That label's OCR merges the heading across the full width, so the
    #   column test cannot separate them and the height test must.
    #
    # A box that fails either test is stepped over rather than ending the
    # block: the warning continues beneath its neighbour. Only a kept line
    # moves the running edge, so a neighbour cannot hold the run open across
    # the gap that ends it.
    #
    # A box the sweep picked up from *above* the heading never widens the
    # column. The statement begins at its own heading, so such a box is
    # dropped from the text a few lines below whatever happens here — but a
    # tequila back prints `HECHO EN MEXICO - BOTTLED AT ORIGIN - DRINK
    # RESPONSIBLY` across the full width just above the warning, and letting
    # that widen the column re-admitted the producer number printed beside it.
    block: list[_Box] = []
    last_bottom: float | None = None
    column_x0, column_x1 = heading.x0, heading.x1
    for b in sorted(below, key=lambda b: b.y0):
        if (b.y1 - b.y0) > line_height * _WARNING_LINE_HEIGHT_MAX:
            continue
        overlap = min(b.x1, column_x1) - max(b.x0, column_x0)
        narrower = min(b.x1 - b.x0, column_x1 - column_x0)
        if narrower > 0 and overlap / narrower < _WARNING_COLUMN_OVERLAP_MIN:
            continue
        if last_bottom is not None and b.y0 - last_bottom > line_height * 2.5:
            break
        block.append(b)
        last_bottom = max(last_bottom or 0.0, b.y1)
        if b.y1 > heading.y0:
            column_x0, column_x1 = min(column_x0, b.x0), max(column_x1, b.x1)

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
            parts[0] = parts[0][opening.start() :]
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


# An origin statement is a statement, so its lead-in opens a segment of the
# line: the start of it, or whatever follows a separator. Reading the lead-in
# anywhere let it match inside a marketing sentence — "…fermented to classical
# music, and distilled in copper pot stills. Our careful process…" returned
# `copper pot stills. Our` as the country of origin — because "distilled in"
# reads the same mid-sentence as it does on a line of its own. The capture
# stops at a full stop followed by a space for the same reason: the run-on
# past the end of the sentence was the other half of that one reading.
#
# "FROM" is only an origin lead-in after PRODUCT or IMPORTED. After the verbs
# that name what was done to the drink it introduces the material and not the
# place: "DISTILLED FROM CORN" and "DISTILLED FROM HEAVILY PEATED MALT" were
# both read as the country of origin. That is the reading that costs a reviewer
# most - a confident wrong answer beside a field, where reading nothing would
# have sent them to look at the label themselves.
#
# The lead-ins are a lexicon for *spotting* the statement and not a list of
# countries, and that distinction is settled outside this module.
# `app/rules/_validators/origin_match.py` records that no country list is
# built anywhere in this product: customs marking accepts the country's name
# in its own language, an abbreviation that unmistakably indicates it, and the
# adjectival form, given "by example rather than as a list", so rejecting on
# their account would reject compliant labels. `HECHO EN` is here because that
# same docstring names "HECHO EN MEXICO" as an origin statement — it is a
# lead-in in another language, and the country it leads to is still read off
# the label rather than looked up. The list of lead-ins is open by nature: a
# statement it does not know is read as no statement at all, which the origin
# rule treats as unsettled rather than as a rejection.
_ORIGIN_RE = re.compile(
    r"(?:^|(?<=[^\w\s])|(?<=[^\w\s]\s))"
    r"(?:(?:PRODUCT|PRODUCE|PRODUCED|MADE|BREWED|DISTILLED|BOTTLED|IMPORTED)"
    r"\s+(?:OF|IN)|(?:PRODUCT|IMPORTED)\s+FROM|HECHO\s+EN)\s+(?:THE\s+)?"
    r"([A-Za-z][\w.]*(?:(?<!\.)\s+(?:AND\s+|OF\s+)?[A-Za-z][\w.]*){0,3})",
    re.I,
)

# The same words that state a country state a State: a label reading
# "DISTILLED IN INDIANA" is not declaring a country of origin. A place on this
# list is not reported as one.
_US_STATES = frozenset(
    [
        "ALABAMA",
        "ALASKA",
        "ARIZONA",
        "ARKANSAS",
        "CALIFORNIA",
        "COLORADO",
        "CONNECTICUT",
        "DELAWARE",
        "FLORIDA",
        "GEORGIA",
        "HAWAII",
        "IDAHO",
        "ILLINOIS",
        "INDIANA",
        "IOWA",
        "KANSAS",
        "KENTUCKY",
        "LOUISIANA",
        "MAINE",
        "MARYLAND",
        "MASSACHUSETTS",
        "MICHIGAN",
        "MINNESOTA",
        "MISSISSIPPI",
        "MISSOURI",
        "MONTANA",
        "NEBRASKA",
        "NEVADA",
        "OHIO",
        "OKLAHOMA",
        "OREGON",
        "PENNSYLVANIA",
        "TENNESSEE",
        "TEXAS",
        "UTAH",
        "VERMONT",
        "VIRGINIA",
        "WASHINGTON",
        "WISCONSIN",
        "WYOMING",
    ]
) | frozenset(
    {
        "NEW HAMPSHIRE",
        "NEW JERSEY",
        "NEW MEXICO",
        "NEW YORK",
        "NORTH CAROLINA",
        "NORTH DAKOTA",
        "RHODE ISLAND",
        "SOUTH CAROLINA",
        "SOUTH DAKOTA",
        "WEST VIRGINIA",
        "DISTRICT OF COLUMBIA",
        "PUERTO RICO",
    }
)
_NAME_LEAD_IN_RE = re.compile(
    r"\b(?:BOTTLED|PRODUCED|DISTILLED|IMPORTED|BREWED|PACKED|VINTED|BLENDED|"
    r"MANUFACTURED|CANNED)(?:\s+AND\s+\w+)?\s+(?:BY|FOR)\b[:\s]*",
    re.I,
)
# A city and the State after it, as the label prints them. The State may be
# its postal code or its name written out, and the two are the same State:
# `app/rules/_validators/name_address_match.py` folds one into the other
# before it compares, because "the label and the registry routinely differ on
# which they write". Reading only the code left a label printing "STAMFORD,
# CONNECTICUT" with no city at all. The names are `_US_STATES` above, which
# this module already carries for the origin statement; nothing new is listed.
_STATE_NAMES = "|".join(
    re.escape(name).replace(r"\ ", r"\s+")
    # Longest first, so "WEST VIRGINIA" is not read as "VIRGINIA".
    for name in sorted(_US_STATES, key=len, reverse=True)
)
_CITY_STATE_RE = re.compile(
    # The names are matched whatever case the label sets them in; the
    # postal code stays upper case, which is the only way it is printed.
    rf"([A-Z][A-Za-z.\- ]{{2,}}),\s*((?i:{_STATE_NAMES})|[A-Z]{{2}})\b"
)

# Plain OCR returns lines, not labelled fields, so the class/type line is
# found by the designations that can appear on it. This is a lexicon for
# spotting the line, not a list of what is allowed: which designations the
# application and the regulations accept is the rule pack's to say.
_CLASS_WORDS = (
    "WHISKEY",
    "WHISKY",
    "BOURBON",
    "RYE",
    "SCOTCH",
    "VODKA",
    "GIN",
    "RUM",
    "TEQUILA",
    "MEZCAL",
    "BRANDY",
    "COGNAC",
    "LIQUEUR",
    "CORDIAL",
    "SCHNAPPS",
    "ABSINTHE",
    "GRAPPA",
    "AQUAVIT",
    "SOJU",
    "SAKE",
    "WINE",
    "CHAMPAGNE",
    "PROSECCO",
    "SPARKLING",
    "CHARDONNAY",
    "MERLOT",
    "CABERNET",
    "SAUVIGNON",
    "PINOT",
    "RIESLING",
    "ZINFANDEL",
    "SANGIOVESE",
    "SYRAH",
    "SHIRAZ",
    "MALBEC",
    "TEMPRANILLO",
    "MOSCATO",
    "ROSE",
    "PORT",
    "SHERRY",
    "VERMOUTH",
    "CIDER",
    "MEAD",
    "BEER",
    "ALE",
    "LAGER",
    "STOUT",
    "PORTER",
    "PILSNER",
    "IPA",
    "MALT BEVERAGE",
    "SAISON",
    "BOCK",
    "HEFEWEIZEN",
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
                "text": "",
                "heading_text": "",
                "heading_all_caps": False,
                "heading_bold": False,
                "type_size_pt": 0.0,
                "confidence": 0.0,
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
        # The label's own wording, alongside the number. The format rules judge
        # how the label phrases its alcohol statement, which the number alone
        # cannot show; they name this key in `evidence_required: [alc_text]`
        # (`docs/decisions.md#0011`).
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
        out["abv"] = ({"abv_pct": None, "unit": "", "alc_text": "", "confidence": 0.0}, None, None)

    # -- net contents -----------------------------------------------------
    net = _net_contents(body)
    net_box = net[0] if net is not None else None
    if net is not None:
        net_box, net_match, net_amount = net
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
            {"net_contents_value": None, "unit": "", "confidence": 0.0},
            None,
            None,
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
        brand_block = _display_block(body, brand_box, taken)
        text = " ".join(b.text.strip() for b in brand_block if b.text.strip())
        out["brand_name"] = (
            {
                "brand_name": text,
                "confidence": _confidence("brand_name", brand_block),
            },
            _block_bbox(brand_block),
            text,
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
    """The box set in the largest type whose text satisfies `predicate`.

    Type size is what a label uses to say which words matter most, so the
    largest line is the best reading of a field plain OCR does not label. Size
    is `_Box.type_size` and not height, because a line running up the side of a
    label is tall without being large — and the one line most often printed
    that way is the health warning, which is then the tallest thing on the
    label and was read as its brand.
    """
    candidates = [b for b in boxes if b.text.strip() and predicate(b.text)]
    if not candidates:
        return None
    return max(candidates, key=lambda b: b.type_size)


def _block_bbox(block: list[_Box]) -> tuple[int, int, int, int]:
    """One box around every line of a block, for the region a reviewer is shown."""
    return (
        int(min(b.x0 for b in block)),
        int(min(b.y0 for b in block)),
        int(max(b.x1 for b in block)),
        int(max(b.y1 for b in block)),
    )


def _display_block(boxes: list[_Box], anchor: _Box, exclude: set[str]) -> list[_Box]:
    """The lines set as one display block with `anchor`, in reading order.

    The brand is the one mandatory element with no lead-in words, no unit and
    no fixed wording, so it is found by how it is set rather than by what it
    says — and the tallest line is only ever part of it. Labels set a mark over
    several lines ("Hop" over "Butcher" over "FOR THE WORLD") or across one
    ("LOST" beside "LANTERN"), and the engine returns a box for each, so the
    tallest box alone reports a fragment of the name.

    A line belongs with the anchor when a reader would see it as the same
    block: set at a size of the same order, and close enough to it in both
    directions relative to that size. Size is `_Box.type_size` throughout, so a
    line running up the side of the label is not mistaken for large type. The
    block grows one line at a time, so a mark whose lines step down in size is
    followed the way a person follows it.

    Lines already read as another mandatory element are left out: a label that
    sets its class designation directly under the brand has two elements there,
    not one long name.

    A line carrying no letters can still join. "BENT 301" and "No. 66" are
    marks, and nothing structural separates the number in a brand from an age
    statement set in the same block — so the reading may carry a word the name
    does not. That is a reviewer seeing more of the label than the brand field,
    which is the safe direction: the reading is evidence, and a name reported
    short is a name the reviewer cannot find.
    """
    block = [anchor]
    floor = anchor.type_size * _BLOCK_MIN_HEIGHT_RATIO
    max_dy = anchor.type_size * _BLOCK_MAX_VERTICAL_GAP
    max_dx = anchor.type_size * _BLOCK_MAX_HORIZONTAL_GAP

    remaining = [
        b
        for b in boxes
        if b is not anchor
        and b.text.strip()
        and b.text.strip() not in exclude
        and b.type_size >= floor
    ]

    grew = True
    while grew:
        grew = False
        x0 = min(b.x0 for b in block)
        x1 = max(b.x1 for b in block)
        y0 = min(b.y0 for b in block)
        y1 = max(b.y1 for b in block)
        for box in list(remaining):
            dx = max(0.0, x0 - box.x1, box.x0 - x1)
            dy = max(0.0, y0 - box.y1, box.y0 - y1)
            if dx <= max_dx and dy <= max_dy:
                block.append(box)
                remaining.remove(box)
                grew = True

    return _reading_order(block)


def _only_a_lead_in(text: str) -> bool:
    """Is this box nothing but the lead-in — "PRODUCED BY:" and no name?

    A label that sets the lead-in on its own line gives the engine a box with
    no business in it. Taken as a name it reported the label's own boilerplate
    as the applicant.
    """
    if not _NAME_LEAD_IN_RE.search(text):
        return False
    return not _NAME_LEAD_IN_RE.sub("", text, count=1).strip(" ,.:;-")


def _beneath(box: _Box, boxes: list[_Box], *, limit: int) -> list[_Box]:
    """The boxes that continue `box` down its own column, nearest first.

    A name-and-address block runs down the label, and `_reading_order`
    interleaves columns row by row. On a label printing two blocks side by
    side — "PRODUCED BY:" on the left, "IMPORTED BY:" on the right — the next
    box in reading order therefore belongs to the *other* block, and the
    importer's block was read as ending at the producer's lead-in. A
    continuation sits below the lead-in and overlaps it across the label.
    """
    x0, _, x1, _ = box.as_bbox()
    below = [
        other
        for other in boxes
        if other is not box
        and other.y0 >= box.y0
        and min(x1, other.as_bbox()[2]) > max(x0, other.as_bbox()[0])
    ]
    below.sort(key=lambda other: other.y0)
    return below[:limit]


def _name_address(boxes: list[_Box], joined: str):
    """The applicant's name and address, found by the words in front of it.

    A label prints the block behind a lead-in — "BOTTLED BY", "IMPORTED BY" —
    and follows the name with a city and a State. Both are looked for; what is
    found is reported and what is not is left empty.
    """
    empty = ({"name": "", "city": "", "state": "", "confidence": 0.0}, None, None)
    ordered = _reading_order(boxes)
    for box in ordered:
        lead_in = _NAME_LEAD_IN_RE.search(box.text)
        if not lead_in:
            continue
        # The name may finish the lead-in's own line or begin the next.
        tail = box.text[lead_in.end() :].strip(" ,.:;")
        following = _beneath(box, boxes, limit=3)
        parts = [tail] + [b.text.strip() for b in following]
        used = [box, *following]
        name, city, state = "", "", ""
        for part in parts:
            if not part:
                continue
            place = _CITY_STATE_RE.search(part)
            if place and not city:
                city, state = place.group(1).strip(), place.group(2)
                # One box often carries the name and then the place —
                # "JUAN LOBO TEQUILA, LLC BUDA, TEXAS". What comes before the
                # place is the name, so it is cut out rather than discarded
                # along with the part that held it.
                head = part[: place.start()].strip(" ,.:;")
                if head and not name and not _only_a_lead_in(head):
                    name = head
            elif not name and not _only_a_lead_in(part):
                name = part
            if name and city:
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
