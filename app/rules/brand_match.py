"""Brand-name staging. Pure functions.

  canonicalize       — the normalisation this project's research specifies for
                       a compared value: NFKC, curly quotes and apostrophes to
                       straight ones, the trademark glyphs dropped, accents
                       folded away, runs of whitespace to one space, trimmed,
                       case-folded. Punctuation is kept, because dropping it
                       can change a name.

  stage_a_normalized — True iff two values are equal once canonicalized.

  stage_a_word_run   — True iff one value's whole words appear inside the
                       other's as a consecutive run. A brand mark carrying the
                       declared brand with a word missing or added is the same
                       brand written shorter or longer, not a different one.

  stage_b_fuzzy      — Jaro-Winkler similarity of the canonicalized strings,
                       in [0, 1].

  stage_b_first_letter_variant
                     — the same similarity with a disagreeing first character
                       removed from both sides, and 0.0 when the first
                       characters already agree. The first letter of a
                       stylised brand mark is the character a reader is most
                       likely to lose, and Jaro-Winkler punishes exactly that
                       hardest: its prefix bonus is zero the moment the first
                       characters differ.

Threshold values do NOT live here — they come from rule-pack data, never from
constants in Python. What a score above a threshold *means* is the validator's;
this module only measures.
"""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz.distance import JaroWinkler

from app.rules._validators._helpers import normalize_words, word_run_present

# Curly quotes and apostrophes read as their straight counterparts. A label set
# in a display face routinely prints the curly form where the application types
# the straight one, and the two are the same character to a reader.
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
_TRADEMARK_RE = re.compile(r"[®™©]")
# An article in front of a mark is not part of the mark. It is dropped only
# when comparing word runs, never from the canonical string, so that the
# normalized equality test stays exactly the normalisation the research names.
_ARTICLES = frozenset({"the"})


def canonicalize(s: str) -> str:
    """One value reduced to the form two values are compared in."""
    # The glyphs go first, before NFKC: NFKC rewrites ™ as the letters "TM",
    # and a mark stripped after that is stripped too late — "ACME™" would be
    # compared as "acmetm" and would not match its own name.
    s = _TRADEMARK_RE.sub("", s)
    s = unicodedata.normalize("NFKC", s).translate(_QUOTES)
    # Accents fold away. Every other comparison in the engine folds them
    # (`_helpers.normalize_words`), and a brand that did not was the one place
    # where a label spelling its own name with a diacritic — ŠVYTURYS against
    # an application's SVYTURYS — failed to match itself.
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s).strip().casefold()


def _run_words(s: str) -> tuple[str, ...]:
    words = normalize_words(canonicalize(s))
    return words[1:] if len(words) > 1 and words[0] in _ARTICLES else words


def stage_a_normalized(observed: str, expected: str) -> bool:
    return canonicalize(observed) == canonicalize(expected)


def stage_a_word_run(observed: str, expected: str) -> bool:
    """True when either value's whole words sit inside the other's as a run.

    Whole words, not letters, for the reason `docs/decisions/0007` gives for
    the class-and-type lists: a substring test finds "gin" inside "Virginia".
    """
    a, b = _run_words(observed), _run_words(expected)
    if not a or not b:
        return False
    return word_run_present(a, b) or word_run_present(b, a)


def stage_b_fuzzy(observed: str, expected: str) -> float:
    a = canonicalize(observed)
    b = canonicalize(expected)
    if not a or not b:
        return 0.0
    return JaroWinkler.normalized_similarity(a, b)


def stage_b_first_letter_variant(observed: str, expected: str) -> float:
    """The similarity the two values reach if the first character is a misread.

    0.0 when the first characters agree, so the caller can only ever use this
    to rescue a pair the ordinary score already failed, never to lift one.
    """
    a = canonicalize(observed)
    b = canonicalize(expected)
    if len(a) < 2 or len(b) < 2 or a[0] == b[0]:
        return 0.0
    return JaroWinkler.normalized_similarity(a[1:], b[1:])
