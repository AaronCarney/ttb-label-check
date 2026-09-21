"""The local reader returns the alcohol statement a label prints, and its figure.

Each case is the boxes the OCR engine returned for a real approved label in the
fixture corpus, text, position and score as read, that carry a percentage or
the alcohol words. `_parse` is what turns a reading into the payload the rules
see, so these ask it the question it is asked in production.
"""

from __future__ import annotations

import pytest

from app.vision.local import _Box, _parse


def _box(x0: float, y0: float, x1: float, y1: float, text: str, score: float) -> _Box:
    return _Box(x0=x0, y0=y0, x1=x1, y1=y1, text=text, score=score)


def _abv(*boxes: _Box) -> dict:
    return _parse(boxes=list(boxes), warning_boxes=[], rotation=0)["abv"][0]


def test_a_statement_that_puts_the_words_before_the_figure_is_returned_whole() -> None:
    # ttb-26238001000795, front
    payload = _abv(_box(437.0, 851.0, 605.0, 896.0, "ALC. BY VOL. 5%", 0.9815))
    assert payload["alc_text"] == "ALC. BY VOL. 5%"
    assert payload["abv_pct"] == 5.0


@pytest.mark.parametrize(
    "statement",
    ["ALC./VOL. 8.0%", "ALC. / VOL. 8.0 %", "ALCOHOL BY VOLUME: 40%", "Alc. by vol. 12%"],
)
def test_each_words_first_form_is_returned_whole(statement) -> None:
    payload = _abv(_box(0.0, 0.0, 400.0, 40.0, statement, 0.99))
    assert payload["alc_text"] == statement


def test_a_percentage_inside_a_larger_number_is_not_a_figure() -> None:
    # ttb-26239001000081, front: "100% GRAIN NEUTRAL SPIRITS" is read before the
    # alcohol statement, and its last two digits are not an alcohol content.
    payload = _abv(
        _box(112.0, 1011.0, 943.0, 1057.0, "100% GRAIN NEUTRAL SPIRITS", 0.9939),
        _box(147.0, 1125.0, 277.0, 1154.0, "80 PROOF", 0.9993),
        _box(443.0, 1124.0, 615.0, 1153.0, "40% ALC/VOL", 0.9983),
    )
    assert payload["abv_pct"] == 40.0
    assert payload["alc_text"] == "40% ALC/VOL"
    # The proof in its own box on the same line is kept beside the statement,
    # which is left as it was read.
    assert [(p["value"], p["beside_abv"]) for p in payload["proof"]] == [("80", True)]
    assert payload["proof"][0]["confidence"] == 0.9993


def test_a_percentage_printed_with_the_alcohol_words_wins_over_one_printed_without() -> None:
    # ttb-26239001000239, front: a grape blend is read before the statement.
    payload = _abv(
        _box(
            45.0, 162.0, 446.0, 198.0, "32,5% CLAIRETTE, 32% ROUSSANNE, 30% GRENACHE BLANC,", 0.9869
        ),
        _box(173.0, 193.0, 315.0, 219.0, "5.5% BOURBOULENC", 0.999),
        _box(239.0, 378.0, 414.0, 405.0, "ALC. 14 % BY VOL.", 0.9971),
    )
    assert payload["abv_pct"] == 14.0
    assert payload["alc_text"] == "ALC. 14 % BY VOL."


def test_a_bare_percentage_is_still_read_where_no_statement_carries_the_words() -> None:
    payload = _abv(_box(0.0, 0.0, 400.0, 40.0, "12.5%", 0.99))
    assert payload["abv_pct"] == 12.5
    assert payload["alc_text"] == "12.5%"


# ---------------------------------------------------------------------------
# Proof, which 27 CFR §5.65(b)(1)(i) lets a label state beside its ABV
# ---------------------------------------------------------------------------


def _proofs(*boxes: _Box) -> list[tuple[str, bool]]:
    return [(p["value"], p["beside_abv"]) for p in _abv(*boxes)["proof"]]


def test_a_proof_inside_the_alcohol_statement_is_kept_beside_it() -> None:
    # The brief's own example.
    assert _proofs(_box(0.0, 0.0, 500.0, 40.0, "45% Alc./Vol. (90 Proof)", 0.98)) == [("90", True)]


def test_a_proof_printed_before_the_statement_on_the_same_line_is_beside_it() -> None:
    assert _proofs(
        _box(0.0, 0.0, 120.0, 30.0, "80 PROOF", 0.99),
        _box(140.0, 0.0, 300.0, 30.0, "40% ALC/VOL", 0.99),
    ) == [("80", True)]


def test_the_reversed_form_is_read() -> None:
    assert _proofs(
        _box(0.0, 0.0, 200.0, 30.0, "40% ALC/VOL", 0.99),
        _box(0.0, 36.0, 200.0, 66.0, "PROOF 80", 0.99),
    ) == [("80", True)]


def test_a_proof_on_the_line_below_the_statement_is_beside_it() -> None:
    # ttb-26218001000369: "Alc. 42.8% by vol." over "85.6 US PROOF".
    assert _proofs(
        _box(0.0, 0.0, 260.0, 30.0, "Alc. 42.8% by vol.", 0.99),
        _box(10.0, 36.0, 250.0, 66.0, "85.6 US PROOF", 0.99),
    ) == [("85.6", True)]


def test_a_figure_and_the_word_in_separate_boxes_on_one_line_are_one_proof() -> None:
    assert _proofs(
        _box(0.0, 0.0, 200.0, 30.0, "40% ALC/VOL", 0.99),
        _box(220.0, 0.0, 260.0, 30.0, "80", 0.97),
        _box(270.0, 0.0, 380.0, 30.0, "PROOF", 0.99),
    ) == [("80", True)]


def test_the_corpus_run_on_statement_gives_its_proof() -> None:
    # tests/fixtures/labels/manifest.json: "40%ALC/VOL/80 PROOF".
    assert _proofs(_box(0.0, 0.0, 400.0, 30.0, "40%ALC/VOL/80 PROOF", 0.99)) == [("80", True)]


def test_a_proof_far_from_the_statement_is_kept_but_not_beside_it() -> None:
    assert _proofs(
        _box(0.0, 0.0, 200.0, 30.0, "40% ALC/VOL", 0.99),
        _box(0.0, 600.0, 200.0, 630.0, "90 PROOF", 0.99),
    ) == [("90", False)]


def test_a_class_range_is_not_a_proof() -> None:
    assert (
        _proofs(
            _box(0.0, 0.0, 300.0, 30.0, "VODKA 80-89 PROOF", 0.99),
            _box(0.0, 36.0, 200.0, 66.0, "40% ALC/VOL", 0.99),
        )
        == []
    )


def test_a_distillation_proof_beside_the_statement_is_not_the_bottles() -> None:
    assert (
        _proofs(
            _box(0.0, 0.0, 200.0, 30.0, "40% ALC/VOL", 0.99),
            _box(0.0, 36.0, 300.0, 66.0, "DISTILLED AT 160 PROOF", 0.99),
        )
        == []
    )


def test_an_impossible_figure_is_kept_as_printed() -> None:
    # "860" is an OCR "86°"; the rule records it as unreadable, never compares it.
    assert _proofs(
        _box(0.0, 0.0, 200.0, 30.0, "43% ALC/VOL", 0.99),
        _box(0.0, 36.0, 200.0, 66.0, "860 PROOF", 0.99),
    ) == [("860", True)]


def test_a_label_with_no_proof_gives_an_empty_list() -> None:
    assert _proofs(_box(0.0, 0.0, 200.0, 30.0, "40% ALC/VOL", 0.99)) == []


def test_a_proof_with_no_alcohol_statement_is_kept_and_not_beside_one() -> None:
    payload = _abv(_box(0.0, 0.0, 200.0, 30.0, "90 PROOF", 0.99))
    assert payload["abv_pct"] is None
    assert [(p["value"], p["beside_abv"]) for p in payload["proof"]] == [("90", False)]
