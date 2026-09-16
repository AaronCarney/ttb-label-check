"""The production reader's field extraction, replayed over frozen readings.

This is the first test in the project that drives the default reader's own
parsing against what the labels actually print. It costs no model, no image and
no network: every reading under `tests/recordings/reader/` was taken once by
`eval/read_accuracy.py --freeze`, and `thaw_reading` turns one back into the
boxes `_parse` takes. The proof that a recording is the reader's own output and
not a stand-in is in `plans/wave3-R.md`: the live run and the replay printed a
byte-for-byte identical scoreboard.

Two things this file is for, beyond the scores.

**It finishes the two `local.py` fixes that could not be finished without it.**
`_parse` is a pure function of the boxes — `test_no_image_and_no_socket_is_opened`
drives every recording with `Image.open` and `socket.socket` booby-trapped — and
the heading measurement sits in the same pixel space as the boxes it was taken
from, which `test_every_heading_box_lies_inside_its_own_frame` checks on real
frozen boxes rather than on a drawn one.

**It asserts its own coverage.** A suite that passes over eleven images and a
suite that passes over sixty-two print the same green line, so the count and the
image list are asserted outright. When the corpus grows, this file fails until
somebody looks at what grew.

Why eleven and not the slice's twelve: `26237001000107/front.jpg` never reaches
the reader at all. `app/vision/quality.py` turns it away as glare, so `extract`
returns one `quality` observation and there is no reading to record. Asserting
twelve would be asserting behaviour the application does not have.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.vision.local import (
    MAX_EDGE_PX,
    _find_heading,
    parse_reading,
    thaw_reading,
)
from eval.read_accuracy import CHECKS, LABELS_ROOT, WARNING_ASSET, _has_reading, _score

RECORDINGS = Path("tests/recordings/reader")

# Slice 1, named in `plans/worklist.md` → "The ladder" §5, minus the one image
# the quality gate rejects. Written out rather than globbed so that a recording
# appearing or disappearing is a failure and not a silent change of subject.
COVERED_IMAGES = frozenset({
    "26212001000085/front.jpg",
    "26212001000085/back.jpg",
    "26229001000034/front.jpg",
    "26229001000034/back.jpg",
    "26230001000420/front.jpg",
    "26230001000420/back.jpg",
    "26237001000107/back.jpg",
    "26239001000132/back.jpg",
    "26240001000454/front.jpg",
    "variants/var-heading-title-case-front.jpg",
    "variants/var-warning-wording-front.jpg",
})

# The seven manifest entries those eleven images belong to. Two are variants:
# `eval/read_accuracy.py` records them and does not score them, because they
# exercise the rules rather than the reader. Here they are scored, because a
# variant's `label_observed` is transcribed from the variant's own image and the
# reader is being asked what it can read off that image.
ENTRIES = (
    "ttb-26212001000085",
    "ttb-26229001000034",
    "ttb-26230001000420",
    "ttb-26237001000107",
    "ttb-26240001000454",
    "var-heading-title-case",
    "var-warning-wording",
)

# What the reader gets wrong today, one line per check it misses, with the cause
# beside it. Every pair not named here must be correct, and every pair named here
# must still be wrong — so a fix cannot land quietly and a regression cannot hide
# behind a line that was already red. **When R6 fixes one, delete its line.**
#
# Three causes account for all but four of them, and they are not four separate
# reader defects:
#
#   (A) the warning block keeps boxes past its own text. `_warning_block` trims
#       the statement at `_BLOCK_END_RE` but returns the untrimmed box list, and
#       `_parse` subtracts that list from the body — so a mandatory element
#       printed under the warning is read correctly by the engine and then thrown
#       away before any field can match it. Measured over these recordings: it
#       swallows `ROSE WINE|ITALY| PRODUCT OF ITALY| 750 ML` and
#       `12% ALC. BY VOL. | CONTAINS SULFITES` on both variants, and
#       `IMPORTED BY JUAN LOBO TEQUILA, LLC BUDA, TEXAS` on `26237001000107/back`.
#   (B) brand is "the largest box that is not another field", which on a label
#       whose warning is set large returns a fragment of the warning.
#   (C) class/type is "the largest box containing a designation word", which
#       returns a retailer's name or a lead-in where one is printed larger.
KNOWN_MISSES: dict[tuple[str, str], str] = {
    ("ttb-26212001000085", "brand"): "B — returned 'MPTION OF ALCOHOLIC BEVERAGE IMPAIRS YOUR', a warning fragment, for 'Terre et Bois de Pradière'",
    ("ttb-26212001000085", "class_type"): "C — returned 'Cognae PefiteChampagne'; the printed designation is 'Cognac XO / Cognac Petite Champagne' and the OCR misread two letters",
    ("ttb-26229001000034", "brand"): "B — returned the class designation 'CRÈME DE CASSIS' for the brand 'BREVIS'",
    ("ttb-26229001000034", "class_type"): "C — returned 'LIQUEUR' where the label prints 'CRÈME DE CASSIS LIQUEUR'",
    ("ttb-26229001000034", "abv"): "the front carries no warning block and the ABV is not on the back; nothing matched",
    ("ttb-26229001000034", "net_contents"): "same: '375mL' is on a face whose box list carries no match for `_NET_RE`",
    ("ttb-26230001000420", "brand"): "B — returned the fragment 'TE OLLECTION' for 'The Bruery'",
    ("ttb-26230001000420", "class_type"): "C — returned the retailer 'Total Wine & More' for 'BARREL-AGED IMPERIAL STOUT'",
    ("ttb-26230001000420", "warning_exact"): "the reader's warning text is not word for word and the answer key says this label's is",
    ("ttb-26237001000107", "abv"): "the front is refused by the quality gate and the back prints no ABV",
    ("ttb-26237001000107", "net_contents"): "same as above",
    ("ttb-26237001000107", "name_address"): "A — 'IMPORTED BY JUAN LOBO TEQUILA, LLC BUDA, TEXAS' is swallowed by the warning block",
    ("ttb-26237001000107", "origin"): "A — the same swallowed box carries the origin words",
    ("ttb-26237001000107", "warning_exact"): "the back's warning is not read word for word",
    ("ttb-26240001000454", "brand"): "B — returned 'NOV' for 'I Heard Cassarole'",
    ("ttb-26240001000454", "class_type"): "C — returned nothing; 'Double India Pale Ale' is handwritten on a keg collar",
    ("ttb-26240001000454", "abv"): "the keg collar's '8%' is not matched",
    ("var-heading-title-case", "brand"): "B — returned the fanciful name 'ROSSASTRO' for the brand 'FABIO SIGNORELLI'",
    ("var-heading-title-case", "class_type"): "A — 'ROSE WINE' is inside a box the warning block swallowed; what is left returns the lead-in 'IMPORTED BY:'",
    ("var-heading-title-case", "abv"): "A — '12% ALC. BY VOL.' is inside a swallowed box",
    ("var-heading-title-case", "net_contents"): "A — '750 ML' is inside a swallowed box",
    ("var-heading-title-case", "name_address"): "C/A — returned the lead-in 'PRODUCED BY:' rather than the importer's name and city",
    ("var-heading-title-case", "origin"): "A — 'PRODUCT OF ITALY' is inside a swallowed box",
    ("var-heading-title-case", "warning_exact"): "the answer key says this variant's wording is exact; the reader's reading of it is not",
    ("var-warning-wording", "brand"): "B — as the other variant; same image but for the warning",
    ("var-warning-wording", "class_type"): "A — as the other variant",
    ("var-warning-wording", "abv"): "A — as the other variant",
    ("var-warning-wording", "net_contents"): "A — as the other variant",
    ("var-warning-wording", "name_address"): "C/A — as the other variant",
    ("var-warning-wording", "origin"): "A — as the other variant",
}

_FACE_ORDER = ("front", "back", "neck", "side")


def _manifest() -> dict:
    return json.loads((LABELS_ROOT / "manifest.json").read_text())


def _entries() -> dict[str, dict]:
    return {e["id"]: e for e in _manifest()["labels"]}


def _recording(relative: str) -> Path:
    return (RECORDINGS / relative).with_suffix(".json")


def _replay(entry: dict) -> dict[str, dict]:
    """One label's merged payloads, from its recordings alone.

    The merge is the reader harness's: faces front first, and the first face
    reporting a value for a field is the one that holds it, because a label's
    elements are spread over its faces and the front carries the ones the
    regulations put in the same field of vision.
    """
    merged: dict[str, dict] = {}
    faces = sorted(
        entry["images"],
        key=lambda f: _FACE_ORDER.index(f) if f in _FACE_ORDER else 9,
    )
    for face in faces:
        recording = _recording(entry["images"][face])
        if not recording.exists():
            continue
        payloads = parse_reading(thaw_reading(json.loads(recording.read_text())))
        for field_id, payload in payloads.items():
            if _has_reading(merged.get(field_id)):
                continue
            if _has_reading(payload):
                merged[field_id] = payload
            else:
                merged.setdefault(field_id, payload)
    return merged


def _scored(label_id: str) -> dict[str, bool | None]:
    entry = _entries()[label_id]
    return _score(entry, _replay(entry), WARNING_ASSET.read_text())


# ---------------------------------------------------------------------------
# Coverage — the suite says how much of the corpus it speaks for
# ---------------------------------------------------------------------------

def test_the_suite_covers_exactly_the_recordings_that_exist() -> None:
    """Eleven images, named. A twelfth appearing is a failure until read."""
    on_disk = {
        json.loads(p.read_text())["image"]
        for p in RECORDINGS.rglob("*.json")
    }
    assert on_disk == COVERED_IMAGES
    assert len(on_disk) == 11


def test_the_covered_images_are_the_corpus_slice_they_claim_to_be() -> None:
    """Every covered image is an image the manifest names, and every entry this
    file scores has at least one of its faces covered."""
    entries = _entries()
    named = {rel for e in entries.values() for rel in e["images"].values()}
    assert COVERED_IMAGES <= named
    for label_id in ENTRIES:
        covered = [
            rel for rel in entries[label_id]["images"].values() if rel in COVERED_IMAGES
        ]
        assert covered, f"{label_id} has no covered face"


def test_the_slice_is_a_fraction_of_the_corpus_and_says_so() -> None:
    """The denominator, asserted rather than assumed: 62 images in the corpus,
    eleven replayed here. R8's accuracy figure is the 62 one and this is not it."""
    entries = _entries()
    corpus = {rel for e in entries.values() for rel in e["images"].values()}
    assert len(corpus) == 62
    assert len(COVERED_IMAGES) == 11


# ---------------------------------------------------------------------------
# The field extraction, against what the labels print
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label_id", ENTRIES)
@pytest.mark.parametrize("check", CHECKS)
def test_the_reader_reports_what_the_label_prints(label_id: str, check: str) -> None:
    got = _scored(label_id)[check]
    if got is None:
        pytest.skip(f"{label_id} carries nothing to score {check} against")

    reason = KNOWN_MISSES.get((label_id, check))
    if reason is None:
        assert got is True, (
            f"{label_id} lost {check}. It was correct when this suite was written. "
            f"Either the change that did this is wrong, or this is a trade a "
            f"decision record has to argue for."
        )
    else:
        assert got is False, (
            f"{label_id} now gets {check} right. Delete its line from KNOWN_MISSES — "
            f"it was recorded as: {reason}"
        )


def test_the_known_misses_table_names_only_real_pairs() -> None:
    """A stale line in the table is a lie about the reader, so the table itself
    is checked: every key is a label this file scores and a check it runs."""
    for label_id, check in KNOWN_MISSES:
        assert label_id in ENTRIES, f"{label_id} is not scored here"
        assert check in CHECKS, f"{check} is not a check"


def test_the_warning_is_found_on_every_label_that_prints_one() -> None:
    """The product's first-priority element, on all seven: `warning_present` is
    the one check with no negative case in the corpus, so it is the one that
    would go quietly wrong."""
    for label_id in ENTRIES:
        assert _scored(label_id)["warning_present"] is True, label_id


# ---------------------------------------------------------------------------
# R1.1 and R1.2, finished here on real frozen boxes
# ---------------------------------------------------------------------------

def test_no_image_and_no_socket_is_opened(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_parse` is pure, proved by breaking everything it must not reach.

    The rung-2 test in `tests/test_vision_reading_frame.py` proves it by reading
    the signature. This proves it by replaying all eleven recordings with
    `PIL.Image.open` and `socket.socket` raising, which also covers whatever
    `_parse` calls.
    """
    import socket

    from PIL import Image

    def no_images(*args: object, **kwargs: object):
        raise AssertionError("_parse opened an image")

    def no_sockets(*args: object, **kwargs: object):
        raise AssertionError("_parse opened a socket")

    monkeypatch.setattr(Image, "open", no_images)
    monkeypatch.setattr(socket, "socket", no_sockets)

    for label_id in ENTRIES:
        assert _replay(_entries()[label_id])


def test_every_heading_box_lies_inside_its_own_frame() -> None:
    """The boxes and the boldness measurement share one pixel space.

    This is the real-data half of the fix in `tests/test_vision_reading_frame.py`.
    The reader shrinks a label longer than `MAX_EDGE_PX` and finds its boxes on
    the copy; the measurement crops a box out of an image and does not rescale.
    Three of these eleven images were shrunk — `26230001000420/front.jpg`,
    2516×1594 for both variant fronts — so the defect's own conditions are
    present in the data, not just in a drawn fixture.

    What it checks: the recorded frame is the shrunk one, and the heading's box
    fits inside it, in the orientation the rotation says it was read at. Against
    the original the box would overhang the frame it is claimed to be in.
    """
    for path in sorted(RECORDINGS.rglob("*.json")):
        data = json.loads(path.read_text())
        reading = thaw_reading(data)
        width, height = reading.frame_size
        assert max(width, height) <= MAX_EDGE_PX, data["image"]

        found = _find_heading(reading.warning_boxes)
        if found is None:
            continue
        heading = found[0]
        # A 90° or 270° frame has the frame's own edges swapped: the warning
        # boxes were computed on the rotated copy.
        frame_w, frame_h = (
            (width, height) if reading.rotation % 180 == 0 else (height, width)
        )
        assert 0 <= heading.x0 < heading.x1 <= frame_w, data["image"]
        assert 0 <= heading.y0 < heading.y1 <= frame_h, data["image"]

        measurement = reading.heading_measurement
        if measurement is not None and measurement.confident:
            # A crop taken from a differently-scaled image would measure
            # characters that have nothing to do with this box's height.
            assert 0 < measurement.mean_character_height <= heading.height + 1, (
                data["image"],
                measurement.mean_character_height,
                heading.height,
            )
            assert 0 < measurement.mean_stroke_width <= measurement.mean_character_height


def test_a_rotated_reading_keeps_the_frame_it_was_read_from() -> None:
    """`26212001000085/front.jpg` is photographed on its side: the upright pass
    finds no heading and the 90° pass does. The recording keeps both box lists,
    and the warning is parsed out of the rotated one — which is the whole reason
    `_Reading` carries `warning_boxes` separately."""
    data = json.loads(_recording("26212001000085/front.jpg").read_text())
    reading = thaw_reading(data)

    assert reading.rotation == 90
    assert reading.boxes != reading.warning_boxes
    assert _find_heading(reading.boxes) is None
    assert _find_heading(reading.warning_boxes) is not None

    warning = parse_reading(reading)["gov_warning"]
    assert "GOVERNMENT WARNING" in warning["text"].upper()
    assert warning["heading_all_caps"] is True
