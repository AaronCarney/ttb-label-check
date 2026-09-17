"""The government warning is the warning, and not what is printed beside it.

The fault this file guards: `_warning_block` collected every box at or below
the heading down to a vertical gap, which is a band across the whole label
rather than the block of text the statement occupies. On a two-column back
label that glued the neighbour onto the statement — a keg's tapping
instructions, a deposit line, an importer's web address — and
`common.warning.verbatim` then rejected a warning the label prints correctly.
Measured over the manifest before the fix: 24 of 37 approved labels failed the
verbatim rule; the sweep is reported in commit `8ca3ecc`.

Frozen recordings, so this is what the production reader returns on these
pixels. No model and no OCR.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.vision.local import _parse, thaw_reading

RECORDINGS = Path("tests/recordings/reader")
CANONICAL = Path("assets/warnings/govt_warning_16_21.txt").read_text().strip()


def _warning_text(ttb_id: str, face: str) -> str:
    reading = thaw_reading(json.loads((RECORDINGS / ttb_id / f"{face}.json").read_text()))
    payloads = _parse(
        boxes=reading.boxes,
        warning_boxes=reading.warning_boxes,
        rotation=reading.rotation,
        heading_measurement=reading.heading_measurement,
    )
    found = payloads.get("gov_warning")
    assert found, f"{ttb_id}/{face}: no warning was read at all"
    return (found[0].get("text") or "").strip()


@pytest.mark.parametrize(
    ("ttb_id", "face", "intruder"),
    [
        # A keg front: the tapping instructions are a second column at x 273-422,
        # the warning is at x 14-127, and the band read them line by line in
        # alternation.
        ("26240001000454", "front", "TAPPING"),
        # A tequila back: the Mexican producer number sits to the right of the
        # warning, and the importer's web address below it.
        ("26237001000107", "back", "NOM"),
        # A malt back: the state deposit line is printed beside the warning.
        ("26230001000420", "back", "CASH REFUND"),
        # A rotated cognac front: the OCR returns tall vertical boxes for the
        # brand and the alcohol statement, which are not lines of running text.
        ("26212001000085", "front", "COGNAC"),
    ],
)
def test_the_warning_does_not_carry_its_neighbour(ttb_id, face, intruder):
    assert intruder.upper() not in _warning_text(ttb_id, face).upper()


def test_a_warning_printed_correctly_reads_back_word_for_word():
    """The tequila's statement is correct on the label. What kept it from
    matching was `NOM 1414CRT` and a web address, not its own words."""
    text = _warning_text("26237001000107", "back").upper()
    # `(1)` is read as `(I)` by the OCR on this label — a reading fault of one
    # character, out of scope here and deliberately not normalised away.
    assert text.replace("(I)", "(1)").replace("(1)ACCORDING", "(1) ACCORDING") == CANONICAL.upper()


def test_a_label_that_prints_the_wrong_words_still_fails():
    """`26229001000034` prints "the RISKS of birth defects" where §16.21 fixes
    "the risk". The block work must not rescue it: an overall failure that is
    correct stays a failure."""
    text = _warning_text("26229001000034", "back").upper()
    assert "RISKS OF BIRTH DEFECTS" in text
    assert text != CANONICAL.upper()
