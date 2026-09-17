"""brand_match.py measures two brand strings. It decides nothing.

canonicalize(s)
  The one form two brand values are compared in: NFKC, curly quotes and
  apostrophes straightened, ™ ® © dropped, accents folded away, runs of
  whitespace collapsed, trimmed, case-folded. Punctuation is kept — dropping
  it can change a name, and a difference that is invisible to the comparison
  cannot be shown to a reviewer.

stage_a_normalized(observed, expected) -> bool
  True iff the canonical forms are equal.

stage_a_word_run(observed, expected) -> bool
  True iff one value's whole words sit inside the other's as a run.

stage_b_fuzzy(observed, expected) -> float
  Jaro-Winkler similarity of the canonical forms, in [0, 1].

stage_b_first_letter_variant(observed, expected) -> float
  The similarity the two reach with a disagreeing first character dropped
  from both, and 0.0 when their first characters already agree.
"""

from __future__ import annotations

from app.rules.brand_match import (
    canonicalize,
    stage_a_normalized,
    stage_a_word_run,
    stage_b_first_letter_variant,
    stage_b_fuzzy,
)

# ---------------------------------------------------------------------------
# What canonicalize folds away, and what it keeps
# ---------------------------------------------------------------------------


def test_case_and_spacing_fold_away() -> None:
    assert stage_a_normalized("STONE'S  THROW", "Stone's Throw") is True


def test_curly_and_straight_apostrophes_are_the_same_character() -> None:
    """A label set in a display face prints the curly form where the
    application types the straight one. They read as one character."""
    assert stage_a_normalized("Stone’s Throw", "Stone's Throw") is True


def test_trademark_glyphs_are_dropped() -> None:
    assert stage_a_normalized("ACME™", "Acme") is True


def test_accents_fold_away() -> None:
    """The label spells the brand with a diacritic and the registry record
    does not. Every other comparison in the engine folds accents, and a brand
    that did not was the one place a label failed to match its own name."""
    assert stage_a_normalized("ŠVYTURYS", "SVYTURYS") is True


def test_punctuation_is_kept() -> None:
    """The one thing normalisation must not do. Stripping the apostrophe would
    make this pair an exact match, and the envelope would tell a reviewer the
    brand matched the application exactly when it does not. The difference is
    scored instead, by stage_b_fuzzy, and shown."""
    assert stage_a_normalized("Mama's Bourbon", "Mamas Bourbon") is False
    assert stage_b_fuzzy("Mama's Bourbon", "Mamas Bourbon") > 0.92


def test_a_legal_suffix_is_part_of_the_name() -> None:
    """ "Distilling Co." is not boilerplate to be discarded: cutting words off
    a name decides in advance which of them are disposable. The pair still
    lines up, through whole words rather than through a suffix list."""
    assert stage_a_normalized("Stone's Throw", "Stone's Throw Distilling Co.") is False
    assert stage_a_word_run("Stone's Throw", "Stone's Throw Distilling Co.") is True


def test_canonicalize_leaves_a_plain_name_alone() -> None:
    assert canonicalize("  Blue  River Brewing ") == "blue river brewing"


def test_unrelated_names_are_not_equal() -> None:
    assert stage_a_normalized("Acme", "Bizmark") is False


# ---------------------------------------------------------------------------
# Whole-word runs
# ---------------------------------------------------------------------------


def test_a_mark_that_drops_a_word_is_a_run_of_the_declared_brand() -> None:
    assert stage_a_word_run("THE UGLY", "UGLY SWEATER") is True


def test_a_leading_article_is_not_part_of_the_mark() -> None:
    assert stage_a_word_run("The Brewery", "Brewery") is True


def test_a_run_is_whole_words_not_letters() -> None:
    """The reason docs/decisions.md#0007 gives for the class-and-type lists: a
    substring test finds "gin" inside "Virginia"."""
    assert stage_a_word_run("Gin", "Virginia Spirits") is False


def test_unrelated_names_share_no_run() -> None:
    assert stage_a_word_run("Acme", "Bizmark") is False


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------


def test_a_near_spelling_scores_high() -> None:
    score = stage_b_fuzzy("Stone's Throw Bourbon", "Stones Throw Bourbon")
    assert 0.9 <= score <= 1.0


def test_unrelated_names_score_low() -> None:
    assert stage_b_fuzzy("Acme", "Bizmark") < 0.5


def test_an_empty_value_scores_zero() -> None:
    assert stage_b_fuzzy("", "Acme") == 0.0


def test_the_first_letter_variant_rescores_without_the_disagreeing_character() -> None:
    """A stylised capital is the character a reader most often loses, and
    Jaro-Winkler punishes exactly that hardest: its prefix bonus is zero the
    moment the first characters differ."""
    assert stage_b_fuzzy("Gallo", "QALIO") < 0.85
    assert stage_b_first_letter_variant("Gallo", "QALIO") > 0.85


def test_the_first_letter_variant_is_zero_when_the_first_letters_agree() -> None:
    """So a caller can only ever use it to rescue a pair the ordinary score
    already failed, never to lift one."""
    assert stage_b_first_letter_variant("Blue River Brewing", "Blue River Distillery") == 0.0


def test_the_first_letter_variant_does_not_rescue_a_different_name() -> None:
    assert stage_b_first_letter_variant("Zebra", "Cobra") < 0.85
