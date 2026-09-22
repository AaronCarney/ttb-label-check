"""The proof figures a line of label text states for the bottle's contents.

27 CFR §5.65(b)(1)(i) lets a spirits label state proof beside its alcohol
content, and §5.1 defines proof as twice the percentage of alcohol by volume.
Labels print it many ways, and some numbers followed by "proof" are not the
bottle's proof at all: a registry class range, or the proof the spirit was
distilled at or entered the barrel at.
"""

from __future__ import annotations

import pytest

from app.rules.proof import find_proofs


def _values(text: str) -> list[str]:
    return [p.value for p in find_proofs(text)]


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("90 Proof", "90"),
        ("86° PROOF", "86"),
        ("86 ° PROOF", "86"),
        ("90 US PROOF", "90"),
        ("85.6 US PROOF", "85.6"),
        ("90 U.S. PROOF", "90"),
        ("PROOF 90", "90"),
        ("Proof: 124.6", "124.6"),
        ("90-proof", "90"),
        ("90 PR00F", "90"),
        ("124,6 PROOF", "124.6"),
        ("45% Alc./Vol. (90 Proof)", "90"),
        ("40%ALC/VOL/80 PROOF", "80"),
        ("45% ALC/VOL • 90 PROOF • 750 mL", "90"),
        ("Alcohol by volume: 40% (80 proof)", "80"),
        ("Barrel Proof 124.6", "124.6"),
        ("124.6 BARREL PROOF", "124.6"),
        ("BOTTLED IN BOND 100 PROOF", "100"),
        ("40% ALC/VOL-80 PROOF", "80"),
    ],
)
def test_each_printed_form_gives_the_figure(text: str, value: str) -> None:
    assert _values(text) == [value]


@pytest.mark.parametrize(
    "text",
    [
        "VODKA 80-89 PROOF",
        "VODKA 80 - 89 PROOF",
        "VODKA 80–89 PROOF",
        "DISTILLED AT 160 PROOF",
        "Distilled at 160° proof",
        "BARREL ENTRY PROOF 125",
        "entered the barrel at 125 proof",
        "BULLETPROOF 45",
        "PROOF OF PURCHASE",
        "40% ALC/VOL",
        "1000 PROOF",
    ],
)
def test_what_is_not_the_bottles_proof_gives_nothing(text: str) -> None:
    assert _values(text) == []


def test_a_figure_above_two_hundred_is_kept_as_printed_for_the_caller_to_refuse() -> None:
    # An OCR "86°" read as "860" is not a proof; the finder reports it so the
    # caller can record an unreadable proof rather than miss one silently.
    assert _values("860 PROOF") == ["860"]


def test_the_match_records_where_it_sits_in_the_text() -> None:
    text = "40% ALC/VOL (80 PROOF)"
    (proof,) = find_proofs(text)
    assert text[proof.start : proof.end] == proof.text
    assert "80" in proof.text and "PROOF" in proof.text


def test_two_statements_on_one_line_give_two_figures() -> None:
    assert _values("90 PROOF / PROOF 91") == ["90", "91"]


def test_a_field_label_with_a_colon_belongs_to_the_figure_after_it() -> None:
    # ttb-24002001000626, front: a table of "LABEL: value" pairs, where "80" is
    # the barrels produced and "PROOF:" heads the proof, 96.
    assert _values("PROD: 80 PROOF: 96") == ["96"]
