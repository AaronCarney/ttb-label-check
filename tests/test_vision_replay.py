"""The production reader's field extraction, replayed over frozen readings.

This is the first test in the project that drives the default reader's own
parsing against what the labels actually print. It costs no model, no image and
no network: every reading under `tests/recordings/reader/` was taken once by
`eval/read_accuracy.py --freeze`, and `thaw_reading` turns one back into the
boxes `_parse` takes. The proof that a recording is the reader's own output and
not a stand-in is that the live run and the replay printed a byte-for-byte
identical scoreboard.

Two things this file is for, beyond the scores.

**It finishes the two `local.py` fixes that could not be finished without it.**
`_parse` is a pure function of the boxes — `test_no_image_and_no_socket_is_opened`
drives every recording with `Image.open` and `socket.socket` booby-trapped — and
the heading measurement sits in the same pixel space as the boxes it was taken
from, which `test_every_heading_box_lies_inside_its_own_frame` checks on real
frozen boxes rather than on a drawn one.

**It asserts its own coverage.** A suite that passes over twenty-four images
and a suite that passes over sixty-two print the same green line, so the count
and the image list are asserted outright. When the corpus grows, this file fails
until somebody looks at what grew.

The twenty-four are a first slice of the corpus and every label that prints a
proof statement, both faces of each. The proof labels are here because a proof
read beside the ABV can reject a label, so how the reader finds one on real
boxes is worth pinning without an OCR run.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from app.rules.proof import find_proofs
from app.rules.units import unit_key
from app.vision.local import (
    MAX_EDGE_PX,
    _Box,
    _find_heading,
    _names_a_designation,
    _net_re,
    _parse,
    _units,
    parse_reading,
    thaw_reading,
)
from eval.read_accuracy import CHECKS, LABELS_ROOT, WARNING_ASSET, _has_reading, _score

RECORDINGS = Path("tests/recordings/reader")

# A first slice of the corpus, then the seven labels that print a proof.
# Written out rather than globbed so that a recording appearing or disappearing
# is a failure and not a silent change of subject.
COVERED_IMAGES = frozenset(
    {
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
        "26218001000369/front.jpg",
        "26218001000369/back.jpg",
        "26230001000540/front.jpg",
        "26230001000540/back.jpg",
        "26231001000662/front.jpg",
        "26231001000662/back.jpg",
        "26232001000404/front.jpg",
        "26232001000404/back.jpg",
        "26237001000107/front.jpg",
        "26239001000079/front.jpg",
        "26239001000079/back.jpg",
        "26239001000081/front.jpg",
        "26239001000081/back.jpg",
    }
)

# The thirteen manifest entries those images belong to. Two are variants:
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
    "ttb-26218001000369",
    "ttb-26230001000540",
    "ttb-26231001000662",
    "ttb-26232001000404",
    "ttb-26239001000079",
    "ttb-26239001000081",
)

# The proof each label prints, for the labels that print one.
PRINTED_PROOF = {
    "ttb-26218001000369": "85.6",
    "ttb-26230001000540": "90",
    "ttb-26231001000662": "80",
    "ttb-26232001000404": "80",
    "ttb-26237001000107": "80",
    "ttb-26239001000079": "80",
    "ttb-26239001000081": "80",
}

# What the reader gets wrong today, one line per check it misses, with the cause
# beside it. Every pair not named here must be correct, and every pair named here
# must still be wrong — so a fix cannot land quietly and a regression cannot hide
# behind a line that was already red. **When R6 fixes one, delete its line.**
#
# It was thirty lines when this suite was written. The causes that remain:
#
#   (B) brand is "the largest box that is not another field", which on a label
#       whose warning is set large returns a fragment of the warning. It is the
#       single largest cause left, and it is in none of R6's rows.
#   (C) class/type is "the largest box carrying a designation", which returns a
#       retailer's name where one is printed larger than the designation.
#   (D) the engine never read the characters at all, so no parsing change can
#       reach it. `26229001000034/front.jpg` returned three boxes — `CRÈME DE
#       CASSIS`, `LIQUEUR`, `AEV` — and the label's `375mL` and its alcohol
#       statement are in neither face's box list.
#
# The cause that is gone: the warning block used to keep boxes past its own
# text, so a mandatory element printed under the statement was read correctly by
# the engine and then thrown away before any field could match it. Nine lines
# closed when `_warning_block` began trimming its boxes where it trims its text.
KNOWN_MISSES: dict[tuple[str, str], str] = {
    (
        "ttb-26212001000085",
        "brand",
    ): (
        "B — returned 'MPTION OF ALCOHOLIC BEVERAGE IMPAIRS YOUR', a warning "
        "fragment, for 'Terre et Bois de Pradière'"
    ),
    (
        "ttb-26229001000034",
        "brand",
    ): "B — returned the class designation 'CRÈME DE CASSIS' for the brand 'BREVIS'",
    (
        "ttb-26229001000034",
        "class_type",
    ): "C — returned 'LIQUEUR' where the label prints 'CRÈME DE CASSIS LIQUEUR'",
    (
        "ttb-26229001000034",
        "abv",
    ): (
        "D — the front's alcohol statement came back as the three letters `AEV` "
        "and the back prints none"
    ),
    (
        "ttb-26229001000034",
        "net_contents",
    ): (
        "D — the engine read neither face's `375mL`; the front returned three "
        "boxes and none of them is it"
    ),
    ("ttb-26230001000420", "brand"): "B — returned the fragment 'TE OLLECTION' for 'The Bruery'",
    (
        "ttb-26230001000420",
        "class_type",
    ): "C — returned the retailer 'Total Wine & More' for 'BARREL-AGED IMPERIAL STOUT'",
    ("ttb-26237001000107", "brand"): "B — returned 'LOBO BLUE AG' for 'JUAN LOBO'",
    ("ttb-26237001000107", "warning_exact"): "the back's warning is not read word for word",
    (
        "ttb-26240001000454",
        "class_type",
    ): "C — returned nothing; 'Double India Pale Ale' is handwritten on a keg collar",
    ("ttb-26240001000454", "abv"): "the keg collar's '8%' is not matched",
    (
        "var-heading-title-case",
        "brand",
    ): "B — returned the fanciful name 'ROSSASTRO' for the brand 'FABIO SIGNORELLI'",
    ("var-warning-wording", "brand"): "B — as the other variant; same image but for the warning",
    (
        "ttb-26218001000369",
        "brand",
    ): "B — returned the origin line 'DISTILLED IN IRELAND IRISH' for the brand 'AODH'",
    ("ttb-26218001000369", "class_type"): "C — returned 'WHISKEY' for 'IRISH WHISKEY'",
    (
        "ttb-26218001000369",
        "name_address",
    ): "returned the distiller, not the importer the label names with its address",
    (
        "ttb-26218001000369",
        "origin",
    ): "returned nothing; 'DISTILLED IN IRELAND' was taken as the brand",
    ("ttb-26230001000540", "brand"): "the engine read 'BENT 301' as 'ENT 301'",
    ("ttb-26231001000662", "brand"): "the engine read 'Lucky Lucy's' as 'L3 Jucky Lucy's'",
    ("ttb-26231001000662", "class_type"): "C — returned 'BOURBON' for 'BOURBON WHISKEY'",
    (
        "ttb-26232001000404",
        "class_type",
    ): "the engine read 'Scotch' as 'Sootch'",
    ("ttb-26239001000079", "warning_exact"): "the warning is not read word for word",
    ("ttb-26239001000081", "warning_exact"): "the warning is not read word for word",
}

# Alcohol statements the reader returns other than as printed, with the cause.
# As with KNOWN_MISSES, a fixed one fails until its line is deleted.
STATEMENT_MISSES = {
    "ttb-26232001000404": (
        "the engine read 'alc./vol.' as 'al./vol.', which the statement pattern "
        "does not take, so only '40%' is kept"
    ),
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
    """Twenty-four images, named. Another appearing is a failure until read."""
    on_disk = {json.loads(p.read_text())["image"] for p in RECORDINGS.rglob("*.json")}
    assert on_disk == COVERED_IMAGES
    assert len(on_disk) == 24


def test_the_covered_images_are_the_corpus_slice_they_claim_to_be() -> None:
    """Every covered image is an image the manifest names, and every entry this
    file scores has at least one of its faces covered."""
    entries = _entries()
    named = {rel for e in entries.values() for rel in e["images"].values()}
    assert named >= COVERED_IMAGES
    for label_id in ENTRIES:
        covered = [rel for rel in entries[label_id]["images"].values() if rel in COVERED_IMAGES]
        assert covered, f"{label_id} has no covered face"


def test_the_slice_is_a_fraction_of_the_corpus_and_says_so() -> None:
    """The denominator, asserted rather than assumed: 62 images in the corpus,
    twenty-four replayed here. R8's accuracy figure is the 62 one and this is not it."""
    entries = _entries()
    corpus = {rel for e in entries.values() for rel in e["images"].values()}
    assert len(corpus) == 62
    assert len(COVERED_IMAGES) == 24


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
    the signature. This proves it by replaying every recording with
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
    Three of the first eleven images were shrunk — `26230001000420/front.jpg`,
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
        frame_w, frame_h = (width, height) if reading.rotation % 180 == 0 else (height, width)
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


def test_the_warning_block_gives_back_the_label_lines_it_swept_up() -> None:
    """The warning's box list stops where the warning's text stops.

    `_parse` subtracts the block's boxes from the body before it looks for any
    other element, so a box the block keeps is a box no field can be read from.
    The block already trimmed its *text* at the statement's last words and kept
    the boxes past that point, which discarded mandatory elements the engine had
    read perfectly — on the first eleven recordings, `12% ALC. BY VOL.`, `750 ML`,
    `PRODUCT OF ITALY` and an importer's name and city.

    Checked on the real frozen boxes, in the form the defect took: no box the
    block returns may sit entirely after the statement's end.
    """
    import re

    from app.vision.local import _BLOCK_END_RE, _warning_block

    for path in sorted(RECORDINGS.rglob("*.json")):
        data = json.loads(path.read_text())
        block = _warning_block(thaw_reading(data).warning_boxes)
        if block is None:
            continue
        text, _heading_text, _heading_box, boxes = block
        if not _BLOCK_END_RE.search(text):
            continue
        running = ""
        for box in boxes:
            before = running
            running = re.sub(r"\s+", " ", f"{running} {box.text}").strip()
            assert len(before) < len(text), (
                f"{data['image']}: the block keeps {box.text!r}, which is wholly "
                f"past the statement's end — no other field can be read from it"
            )


def test_the_elements_printed_under_a_warning_are_still_read() -> None:
    """The fix above, stated as what a reviewer would see, on the label that
    prints four of its mandatory elements below the warning statement."""
    payloads = _replay(_entries()["var-heading-title-case"])

    assert payloads["abv"]["abv_pct"] == 12.0
    assert payloads["net_contents"]["net_contents_value"] == 750.0
    assert payloads["net_contents"]["unit"] == "ML"
    assert "ITALY" in payloads["country_origin"]["country"].upper()
    assert "WINE" in payloads["class_type"]["class_type"].upper()


def test_a_boldness_that_could_not_be_measured_is_absent_not_false() -> None:
    """Row 1.2 of the Tier 2 table, on the label that actually produces it.

    `26240001000454/front.jpg` is a handwritten keg collar and its heading's
    stroke width could not be measured — `confident` is False in the recording.
    The payload used to record that as `heading_bold: False`, which is a claim
    about the label rather than about the reading, and it disagreed with
    `app/vision/cloud.py`, which leaves the key alone on the same signal.
    `26230001000420/back.jpg` is the other side of it: measured, and bold.
    """
    unmeasured = parse_reading(
        thaw_reading(json.loads(_recording("26240001000454/front.jpg").read_text()))
    )["gov_warning"]
    assert unmeasured["heading_bold_measured_confident"] is False
    assert "heading_bold" not in unmeasured

    measured = parse_reading(
        thaw_reading(json.loads(_recording("26230001000420/back.jpg").read_text()))
    )["gov_warning"]
    assert measured["heading_bold_measured_confident"] is True
    assert measured["heading_bold"] is True


def test_the_alcohol_statement_is_returned_as_the_label_prints_it() -> None:
    """Row 1.3 of the Tier 2 table, against the manifest's own transcription.

    The reader used to keep the percentage and throw the matched characters
    away, so `format_check.py` compared the rule pack's regex against a sentence
    it had built from those numbers — a check that passed every label it was
    shown (`docs/decisions.md#0011`). `alc_text` is the key the rule packs
    already name in `evidence_required`.

    Compared with spacing collapsed: the transcription is of the label, the
    reading is of the pixels, and `40 % ALC. BY VOL` against `40% ALC. BY VOL`
    is a difference in kerning rather than in wording. A proof printed as part
    of the statement ("40%ALC/VOL/80 PROOF") is reported in the reading's proof
    list, so the statement is also accepted without it.
    """

    def spacing_removed(text: str) -> str:
        return "".join(text.split()).upper().rstrip(".")

    def without_proof(text: str) -> str:
        proofs = find_proofs(text)
        return text[: proofs[0].start].rstrip(" /,(") if proofs else text

    entries = _entries()
    for label_id in ENTRIES:
        payload = _replay(entries[label_id])["abv"]
        assert "alc_text" in payload, label_id
        if payload["abv_pct"] is None:
            assert payload["alc_text"] == "", label_id
            continue
        printed = (entries[label_id]["label_observed"].get("abv") or {}).get("text")
        read = spacing_removed(payload["alc_text"])
        right = read in (spacing_removed(printed), spacing_removed(without_proof(printed)))
        assert right != (label_id in STATEMENT_MISSES), (label_id, payload["alc_text"], printed)


def test_no_label_that_prints_no_proof_is_read_as_stating_one() -> None:
    """On the labels that print no proof, every number, percentage and "100%"
    is read as something other than a proof.

    A figure read as a proof beside the ABV can reject a label
    (`spirits.alcohol.proof_agrees`), so a stray one here is the regression
    that matters. Every face still carries the list, empty, so the rule reports
    that it does not apply rather than finding no reading at all.
    """
    entries = _entries()
    for label_id in ENTRIES:
        if label_id in PRINTED_PROOF:
            continue
        for image in entries[label_id]["images"].values():
            if image not in COVERED_IMAGES:
                continue
            payload = parse_reading(thaw_reading(json.loads(_recording(image).read_text())))
            assert payload["abv"]["proof"] == [], (image, payload["abv"]["proof"])


def test_every_printed_proof_is_read_beside_the_alcohol_statement() -> None:
    """Each proof label's proof is found, as printed, and nothing else is.

    The figures are gathered across the label's faces, as the face merge
    gathers them, because on some labels the proof and the ABV statement the
    replay keeps are on different faces. Every figure found must sit beside an
    ABV statement: only such a figure can reject, and a printed proof read as
    one that cannot would never be checked.
    """
    entries = _entries()
    for label_id, printed in PRINTED_PROOF.items():
        found = []
        for image in entries[label_id]["images"].values():
            payload = parse_reading(thaw_reading(json.loads(_recording(image).read_text())))
            found.extend(payload["abv"]["proof"])
        assert {p["value"] for p in found} == {printed}, (label_id, found)
        assert all(p["beside_abv"] for p in found), (label_id, found)


def test_the_statement_is_cut_out_of_a_box_that_carries_other_text() -> None:
    """Three real boxes carry the statement alongside something else, and the
    statement returned is the statement rather than the box."""
    readings = {
        "26212001000085/front.jpg": "40% ALC. BY VOL",  # box: '40% ALC. BY VOL-700 mL'
        "26230001000420/front.jpg": "ALC. 20.3% BY VOL.",  # box: '... 12.7 FL. OZ.'
        # box: '... | CONTAINS SULFITES'
        "variants/var-heading-title-case-front.jpg": "12% ALC. BY VOL.",
    }
    for image, statement in readings.items():
        payload = parse_reading(thaw_reading(json.loads(_recording(image).read_text())))["abv"]
        assert payload["alc_text"] == statement, image


# ---------------------------------------------------------------------------
# Row 1.1 — net contents, against every net-contents line the corpus prints
# ---------------------------------------------------------------------------


def _net_contents_of(printed: str) -> dict:
    """What the reader reads off one line of label text.

    `_parse` over a single box. The line is the manifest's own transcription of
    what the label prints, so this asks the extractor the question the answer
    key already has an answer to, without spending a second of OCR to re-read
    pixels that were transcribed by hand.
    """
    box = _Box(x0=0.0, y0=0.0, x1=400.0, y1=40.0, text=printed, score=0.99)
    payloads = _parse(boxes=[box], warning_boxes=[], rotation=0)
    return payloads["net_contents"][0]


def test_every_net_contents_line_in_the_corpus_is_read_as_the_answer_key_reads_it() -> None:
    """Row 1.1, over all thirty-odd net-contents transcriptions in the manifest.

    The reader's unit list used to be written out in `local.py` and it was the
    fourth copy in the app. It knew `ML` and `FL. OZ.` and did not know
    `FL. OUNCES`, `FLUID OUNCES`, `MILLILITRES` or `US GALLONS` — spellings
    `rules/tables/volume_units.yaml` lists and that real labels in this corpus
    print. A unit missing from it produced no reading at all, so the rule pack
    was handed nothing to check on a label that states its contents plainly.

    `amount: null` in the manifest is not a gap: it is the answer key saying the
    line names no single quantity — `15.5 US GALLONS / 10.8 US GALLONS / …` is a
    keg collar with three sizes struck through — and a reader that picks one of
    them is guessing. The reader must report nothing there and let a reviewer
    read the words.
    """
    checked = 0
    for entry in _manifest()["labels"]:
        printed = (entry.get("label_observed") or {}).get("net_contents") or {}
        if not printed.get("text"):
            continue
        checked += 1
        read = _net_contents_of(printed["text"])
        if printed.get("amount") is None:
            assert read["net_contents_value"] is None, (entry["id"], printed["text"], read)
            continue
        assert read["net_contents_value"] == pytest.approx(float(printed["amount"])), (
            entry["id"],
            printed["text"],
            read,
        )
        assert unit_key(read["unit"]) == unit_key(printed["unit"]), (
            entry["id"],
            printed["text"],
            read,
        )
    assert checked >= 30, f"only {checked} net-contents transcriptions found"


def test_the_spelled_out_units_the_old_list_did_not_know() -> None:
    """The four spellings that produced no reading at all, named one by one so a
    regression says which spelling it lost."""
    for printed, amount, unit in (
        ("11.2 FL. OUNCES", 11.2, "FL. OUNCES"),  # ttb-26239001000217
        ("15.5 US GALLONS", 15.5, "US GALLONS"),  # ttb-26240001000454's first size
        ("12 FLUID OUNCES", 12.0, "FLUID OUNCES"),
        ("750 MILLILITRES", 750.0, "MILLILITRES"),
    ):
        read = _net_contents_of(printed)
        assert read["net_contents_value"] == pytest.approx(amount), printed
        assert unit_key(read["unit"]) == unit_key(unit), printed


def test_the_metric_figure_is_the_declaration_where_a_line_prints_both() -> None:
    """`NET CONT. 350 ML / 12 FL OZ` is one quantity written twice, and the
    application declares net contents in millilitres — so the metric figure is
    the declaration and the customary one is that same quantity rounded. The
    reader used to return whichever the box order put first."""
    read = _net_contents_of("NET CONT. 350 ML / 12 FL OZ")
    assert read["net_contents_value"] == pytest.approx(350.0)
    assert unit_key(read["unit"]) == "ml"

    reversed_order = _net_contents_of("NET CONT. 12 FL OZ / 350 ML")
    assert reversed_order["net_contents_value"] == pytest.approx(350.0)
    assert unit_key(reversed_order["unit"]) == "ml"


def test_a_compound_statement_is_not_reported_as_its_first_half() -> None:
    """`1 PT. 9 FL. OZ.` is a pint and nine fluid ounces — 739 mL. The reader
    used to report `1 PT`, 473 mL, which against a declared 739 is a compliant
    bottle failed on the reader's own arithmetic. Nothing here can add the two
    halves up, so the honest reading is no reading."""
    read = _net_contents_of("1 PT. 9 FL. OZ.")
    assert read["net_contents_value"] is None
    assert read["unit"] == ""


def test_adding_a_unit_is_an_edit_to_the_shipped_table_and_nothing_else() -> None:
    """The point of row 1.1, asserted rather than described: every unit the
    reader can read comes from `rules/tables/volume_units.yaml`, so a unit the
    table drops is a unit the reader stops reading."""
    from app.rules.units import table_from_entries

    with_only_hogsheads = table_from_entries([{"unit": "hogshead", "factor": 238480.9}])
    _net_re.cache_clear()
    _units.cache_clear()
    try:
        with mock.patch("app.vision.local._units", lambda: with_only_hogsheads):
            _net_re.cache_clear()
            assert _net_re().search("1 HOGSHEAD") is not None
            assert _net_re().search("750 ML") is None
    finally:
        _net_re.cache_clear()
        _units.cache_clear()


# ---------------------------------------------------------------------------
# Row 1.4 — the class/type lexicon, matched as words rather than as letters
# ---------------------------------------------------------------------------


def test_a_designation_is_matched_as_a_word_and_not_as_letters() -> None:
    """Row 1.4, on the five real box texts it changes.

    The test used to be a substring search over the folded line, so any line
    whose letters happened to spell a designation was a candidate for the
    label's class and type. `_largest_matching` then took the tallest candidate,
    and a lead-in or a web address is often set larger than the designation
    itself.

    Every line below is one the reader actually read off a label in this corpus,
    and every one of them was a candidate before. The reduction is the rule
    pack's own — `app.rules._validators._helpers`, where "gin must not match
    inside Virginia" is already written down.
    """
    for line in (
        "HECHO EN MEXICO - BOTTLED AT ORIGIN - DRINK RESPONSIBLY",  # ORIgiN
        "WWW.JUANLOBOTEQUILA.COM",  # a web address
        "IMPORTED BY:",  # imPORTed
    ):
        assert _names_a_designation(line) is False, line

    # Not a change of subject: the designations the lexicon is for still match,
    # including the multi-word ones.
    for line in (
        "BARREL-AGED IMPERIAL STOUT",
        "CRÈME DE CASSIS LIQUEUR",
        "MALT BEVERAGE",
        "Double India Pale Ale",
        "APPELLATION COGNAC PETITE CHAMPAGNE CONTRÔLÉE",
    ):
        assert _names_a_designation(line) is True, line


def test_a_name_and_address_line_is_not_the_class_and_type() -> None:
    """`IMPORTED BY WINE WINE SITUATION LLC-SIGNAC HILL, CA` is a real line off
    `26212001000085/front.jpg`. Its importer's trade name carries the word
    "wine", the line is set larger than the designation, and it opens with the
    lead-in that says what it is. The words after "imported by" or "bottled by"
    are a business, and a business may be named anything."""
    assert _names_a_designation("IMPORTED BY WINE WINE SITUATION LLC-SIGNAC HILL, CA") is False
    assert _names_a_designation("PRODUCED AND BOTTLED BY STOUT BROTHERS, PORTLAND, OR") is False
    assert _names_a_designation("STOUT") is True


def test_the_cognac_label_now_reads_its_own_designation() -> None:
    """What the two halves of row 1.4 buy, on the one label in the slice that
    turns on them. `26212001000085/front.jpg` prints its designation three
    times: in a stylised `Cognac XO` set larger than anything else on the
    label, in an appellation line, and in a stylised pair the engine ran
    together as `Cognae PefiteChampagne`. The substring test matched the
    garbled one and reported it; with words, the garbled one is not a candidate
    at all.

    Which of the two good candidates wins changed when the warning block became
    a column (`_warning_block`). The band the block used to take swallowed
    `Cognac XO`, so the appellation line was the only candidate left; with the
    block confined to its own column the larger line is visible again and
    `_largest_matching` takes it, which is what "the label says which words
    matter most by how large it sets them" means. The corpus answer key scores
    this label's class and type **correct** either way.
    """
    payloads = parse_reading(
        thaw_reading(json.loads(_recording("26212001000085/front.jpg").read_text()))
    )
    read = payloads["class_type"]["class_type"].upper()
    assert "COGNAC" in read
    assert "PEFITECHAMPAGNE" not in read


# ---------------------------------------------------------------------------
# Rows 1.5-1.7 — the origin statement and the name-and-address block
# ---------------------------------------------------------------------------


def _origin_of(*lines: str) -> dict:
    """What the reader reads as the country of origin off these lines.

    One box per line, stacked down a column the way a label prints them, so
    `_parse` walks them in the order a person would read them.
    """
    boxes = [
        _Box(x0=0.0, y0=float(n * 50), x1=600.0, y1=float(n * 50 + 40), text=line, score=0.99)
        for n, line in enumerate(lines)
    ]
    return _parse(boxes=boxes, warning_boxes=[], rotation=0)["country_origin"][0]


def test_an_origin_lead_in_inside_a_sentence_is_not_an_origin_statement() -> None:
    """Row 1.5, on the line that produced the miss.

    `26237001000107/back.jpg` prints a paragraph of marketing copy, and
    "distilled in" inside it read exactly as it reads on a line of its own. The
    reader returned `copper pot stills. Our` as the label's country of origin —
    a phrase, four words long, running past a full stop.

    An origin statement is a statement, so its lead-in opens a segment of the
    line: the start of it, or whatever follows a separator. That is the whole
    test; no country is named anywhere in the reader.
    """
    marketing = (
        "slow cooked in brick ovens, fermented to classical music,",
        "and distilled in copper pot stills. Our careful process delivers a",
    )
    assert _origin_of(*marketing)["country"] == ""

    # The same lead-in, opening a segment, is read — both at the start of a line
    # and after the separator a label sets between its elements.
    assert _origin_of("PRODUCT OF FRANCE")["country"] == "FRANCE"
    assert _origin_of("ROSE WINE|ITALY| PRODUCT OF ITALY| 750 ML")["country"] == "ITALY"


def test_the_origin_capture_stops_where_the_sentence_does() -> None:
    """The other half of the same miss: the capture ran four words on past the
    full stop. A sentence that has ended has ended."""
    assert _origin_of("PRODUCT OF FRANCE. Our careful process delivers a")["country"] == "FRANCE"


def test_the_origin_statement_in_spanish_is_read_off_the_real_label() -> None:
    """`26237001000107/back.jpg` states its origin as `HECHO EN MEXICO`, on its
    own line, and the manifest transcribes it that way.

    `HECHO EN` is a lead-in, not a country: what follows it is still read off
    the label. `app/rules/_validators/origin_match.py` names "HECHO EN MEXICO"
    as an origin statement in the same docstring that settles that no country
    list is built anywhere in this product, so spotting the lead-in invents
    nothing. A lead-in the reader does not know yields no statement, which the
    origin rule treats as unsettled rather than as a rejection.
    """
    payloads = parse_reading(
        thaw_reading(json.loads(_recording("26237001000107/back.jpg").read_text()))
    )
    assert payloads["country_origin"]["country"].upper() == "MEXICO"


def test_a_state_written_out_is_the_same_state_as_its_postal_code() -> None:
    """Row 1.6. `STAMFORD, CONNECTICUT` is an address and `STAMFORD, CT` is the
    same address; the reader used to see only the second and report no city at
    all for the first.

    `app/rules/_validators/name_address_match.py` already folds a State's name
    into its postal code before it compares, "because the label and the registry
    routinely differ on which they write". The names come from `_US_STATES`,
    which `local.py` already carries for the origin statement.
    """
    from app.vision.local import _CITY_STATE_RE

    for line, city, state in (
        ("STAMFORD, CONNECTICUT", "STAMFORD", "CONNECTICUT"),
        ("STAMFORD, CT", "STAMFORD", "CT"),
        ("HUDSON, NY", "HUDSON", "NY"),
        ("Charleston, West Virginia", "Charleston", "West Virginia"),
    ):
        found = _CITY_STATE_RE.search(line)
        assert found is not None, line
        assert (found.group(1), found.group(2)) == (city, state), line

    # A word that is not a State does not make the line an address.
    assert _CITY_STATE_RE.search("KLOCKE ESTATE DISTILLERY, LLC") is None


def test_a_lead_in_on_its_own_line_is_not_a_business_name() -> None:
    """Row 1.7, on both variant fronts, which is where the miss was read.

    That label prints two blocks side by side — "PRODUCED BY:" on the left,
    "IMPORTED BY:" on the right — each lead-in a box of its own with its
    business on the line below. `_reading_order` interleaves columns row by row,
    so the box after "IMPORTED BY:" was the *other* block's lead-in, and the
    reader reported `PRODUCED BY:` as the applicant's name with no city at all.

    A block continues down its own column, and a box that is nothing but a
    lead-in is not a name.
    """
    for label_id in ("var-heading-title-case", "var-warning-wording"):
        payload = _replay(_entries()[label_id])["name_address"]
        assert payload["name"] == "WHITSERVELLC", label_id
        assert payload["city"] == "STAMFORD", label_id
        assert payload["state"] == "CONNECTICUT", label_id


def test_a_box_carrying_the_name_and_the_place_gives_up_both() -> None:
    """`26237001000107/back.jpg` prints its whole block on one line —
    `IMPORTED BY JUAN LOBO TEQUILA, LLC BUDA, TEXAS`. Recognising the State
    written out would otherwise have cost the name, because the name used to be
    the first part of the block that carried no place in it."""
    payload = parse_reading(
        thaw_reading(json.loads(_recording("26237001000107/back.jpg").read_text()))
    )["name_address"]
    assert payload["name"] == "JUAN LOBO TEQUILA"
    assert payload["state"] == "TEXAS"
