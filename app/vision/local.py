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
import re
import time
import unicodedata
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO

import numpy as np
from PIL import Image

from app.config import Settings
from app.schemas.calls import CallRecord
from app.schemas.expected import BeverageClass
from app.schemas.extracted import Evidence, EvidenceSource, FieldObservation, MatchKind
from app.schemas.label import Label
from app.vision import quality
from app.vision.heading_measure import measure_heading_bold

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
        self._load_lock = asyncio.Lock()

    # -- lifecycle ---------------------------------------------------------

    def _load(self) -> object:
        """Build the engine. Blocking: the models are read off disk."""
        from rapidocr import RapidOCR

        return RapidOCR()

    async def ensure_loaded(self) -> None:
        """Load this instance's models before a read rather than during one.

        The load costs about a second and blocks, so it runs in a thread behind
        a lock: concurrent callers wait on the one load instead of each building
        an engine. The engine is per instance, and ``app/deps.py`` builds a new
        extractor for every request, so that second is currently paid for every
        label. Paying it once would mean one reader shared by the process.
        """
        if self._engine is not None:
            return
        async with self._load_lock:
            if self._engine is None:
                self._engine = await asyncio.to_thread(self._load)

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
        payloads, meta = await asyncio.to_thread(self._read, label.image_bytes)
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

    def _read(self, image_bytes: bytes) -> tuple[dict, dict]:
        """OCR one image and cut its text into the seven fields.

        Returns the per-field payloads and a small record of how the read went,
        which the audit trail carries.
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
        if not _find_heading(boxes):
            for angle in (90, 270):
                rotated = image.rotate(angle, expand=True)
                candidate = self._boxes(rotated)
                if _find_heading(candidate):
                    warning_boxes, rotation, warning_image = candidate, angle, rotated
                    break

        rotated_bytes = image_bytes
        if rotation:
            buffer = BytesIO()
            warning_image.save(buffer, format="PNG")
            rotated_bytes = buffer.getvalue()

        payloads = _parse(
            boxes=boxes,
            warning_boxes=warning_boxes,
            warning_image_bytes=rotated_bytes,
            rotation=rotation,
        )
        meta = {
            "reader": "local",
            "engine": "rapidocr",
            "rotation_deg": rotation,
            "boxes_found": len(boxes),
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
    parts = [b.text for b in ordered if b.text.strip()]
    if parts:
        opening = re.search(r"GOVERNMENT\s*WARNING", parts[0], re.I)
        if opening:
            parts[0] = parts[0][opening.start():]
    text = re.sub(r"\s+", " ", " ".join(parts)).strip()

    # The statement ends at its own last words. Anything the block swept up
    # after them belongs to the label, not to the warning.
    end = _BLOCK_END_RE.search(text)
    if end:
        text = text[: end.end()]

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
_NET_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(ML|MLS|MILLILITERS?|L|LITERS?|LITRES?|CL|"
    r"FL\.?\s*OZ\.?|OZ\.?|PINTS?|PT|QUARTS?|QT|GALLONS?|GAL)\b",
    re.I,
)
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
    warning_image_bytes: bytes,
    rotation: int,
) -> dict[str, tuple[dict, tuple[int, int, int, int] | None, str | None]]:
    """Every field's payload, its box and the text it was read from."""
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
        measurement = measure_heading_bold(warning_image_bytes, heading_box.as_bbox())
        factor = _ROTATED_FRAME_PENALTY if rotation else 1.0
        payload = {
            "text": text,
            "heading_text": heading_text,
            "heading_all_caps": bool(letters) and all(c.isupper() for c in letters),
            "heading_bold": measurement.is_bold if measurement.confident else False,
            # The reader reports no type size: a photograph does not carry the
            # scale that would turn pixels into points. Decision 0006 puts the
            # rules that need one out of scope.
            "type_size_pt": 0.0,
            "confidence": _confidence("gov_warning", block_boxes, factor=factor),
            "heading_bold_measured": measurement.is_bold,
            "heading_bold_measured_confident": measurement.confident,
            "heading_bold_width_height_ratio": measurement.width_height_ratio,
        }
        out["gov_warning"] = (payload, heading_box.as_bbox(), text)

    warning_texts = {b.text for b in (block[3] if block else [])}
    body = [b for b in boxes if b.text not in warning_texts]
    joined = " ".join(b.text for b in _reading_order(body))

    # -- alcohol content --------------------------------------------------
    abv_box, abv_match = _first_match(body, _ABV_RE)
    if abv_match:
        raw = next(g for g in abv_match.groups() if g)
        out["abv"] = (
            {
                "abv_pct": float(raw.replace(",", ".")),
                "unit": "%",
                "confidence": _confidence("abv", [abv_box]),
            },
            abv_box.as_bbox(),
            abv_match.group(0).strip(),
        )
    else:
        out["abv"] = ({"abv_pct": None, "unit": "", "confidence": 0.0}, None, None)

    # -- net contents -----------------------------------------------------
    net_box, net_match = _first_match(body, _NET_RE)
    if net_match:
        out["net_contents"] = (
            {
                "net_contents_value": float(net_match.group(1).replace(",", ".")),
                "unit": net_match.group(2).upper().replace(".", "").replace(" ", ""),
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
    class_box = _largest_matching(
        body, lambda t: any(word in _fold(t) for word in _CLASS_WORDS)
    )
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
