"""Brand-name match staging. Pure functions.

  stage_a_normalized — NFKC + casefold + strip punctuation + collapse whitespace
                       + drop legal suffixes (Inc, Co, LLC, leading 'The',
                       trademark glyphs). Returns True iff equal.

  stage_b_fuzzy      — RapidFuzz Jaro-Winkler similarity on the canonicalized
                       strings, returning a score in [0, 1].

Threshold values do NOT live here — they come from rule-pack data, never from
constants in Python.
"""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz.distance import JaroWinkler

_LEGAL_SUFFIX_RE = re.compile(
    r"\b(?:inc|inc\.|co|co\.|llc|ltd|ltd\.|corp|corp\.|company|distilling|distillery)\b\.?",
    re.IGNORECASE,
)
_LEADING_THE_RE = re.compile(r"^the\s+", re.IGNORECASE)
_TRADEMARK_RE = re.compile(r"[®™©]")
_PUNCT_RE = re.compile(r"[^\w\s]")


def _canonicalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = _TRADEMARK_RE.sub("", s)
    s = _LEADING_THE_RE.sub("", s)
    s = _LEGAL_SUFFIX_RE.sub("", s)
    s = _PUNCT_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip().casefold()
    return s


def stage_a_normalized(observed: str, expected: str) -> bool:
    return _canonicalize(observed) == _canonicalize(expected)


def stage_b_fuzzy(observed: str, expected: str) -> float:
    a = _canonicalize(observed)
    b = _canonicalize(expected)
    if not a or not b:
        return 0.0
    return JaroWinkler.normalized_similarity(a, b)
