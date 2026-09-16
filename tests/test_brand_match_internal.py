"""brand_match.py provides two pure helpers:

  stage_a_normalized(observed, expected) -> bool
    NFKC + casefold + strip punctuation + collapse whitespace + drop legal
    suffixes (Inc., Co., LLC, leading 'The', ®, ™). Returns True iff the
    normalized strings are equal.

  stage_b_fuzzy(observed, expected) -> float
    RapidFuzz Jaro-Winkler similarity on the same normalized strings, in [0, 1].
"""
from __future__ import annotations

from app.rules.brand_match import stage_a_normalized, stage_b_fuzzy


def test_stage_a_handles_case() -> None:
    assert stage_a_normalized("STONE'S THROW", "Stone's Throw") is True


def test_stage_a_handles_punctuation_strip() -> None:
    assert stage_a_normalized("Mama's Bourbon", "Mamas Bourbon") is True


def test_stage_a_drops_legal_suffix() -> None:
    assert stage_a_normalized("Stone's Throw Distilling Co.", "Stone's Throw Distilling") is True


def test_stage_a_drops_leading_the() -> None:
    assert stage_a_normalized("The Brewery", "Brewery") is True


def test_stage_a_fail_on_substantive_difference() -> None:
    assert stage_a_normalized("Acme", "Bizmark") is False


def test_stage_b_high_score_on_close_strings() -> None:
    score = stage_b_fuzzy("Stone's Throw Bourbon", "Stones Throw Bourbon")
    assert 0.9 <= score <= 1.0


def test_stage_b_low_score_on_unrelated_strings() -> None:
    assert stage_b_fuzzy("Acme", "Bizmark") < 0.5
