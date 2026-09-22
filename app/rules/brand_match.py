"""Brand-name staging. Pure functions.

  canonicalize       — the normalisation this project's research specifies for
                       a compared value: NFKC, curly quotes and apostrophes to
                       straight ones, the trademark glyphs dropped, accents
                       folded away, runs of whitespace to one space, trimmed,
                       case-folded. Punctuation is kept, because dropping it
                       can change a name.

  stage_a_normalized — True iff two values are equal once canonicalized.

  stage_a_punctuation_only
                     — True iff two values are the same once punctuation and
                       spacing are taken out of both. Unicode collation's
                       "ignore punctuation" setting (UTS #10, alternate=shifted)
                       makes the same equivalence: "De Anza", "De-Anza" and
                       "DeAnza" compare equal.

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

from rapidfuzz.distance import JaroWinkler, Levenshtein

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


# Marks that stand for something are part of the name even though Unicode files
# them as punctuation: "A&W" is not "AW", "#7" is not "7", and "7%" is not "7".
_SIGNIFICANT_MARKS = frozenset("&#@%")
# Characters labels and readers print for an apostrophe or a prime that Unicode
# does not file as punctuation: the grave and acute accents stand alone, the
# modifier-letter apostrophe, and the prime. They are the same mark to a reader.
_APOSTROPHE_LIKE = frozenset(
    "`\N{ACUTE ACCENT}\N{MODIFIER LETTER APOSTROPHE}\N{PRIME}\N{DOUBLE PRIME}"
)


def _ignorable(s: str, i: int) -> bool:
    """Whether the character at `i` is punctuation or spacing a name can lose.

    A mark between two digits is not: it is part of a number, and "1.5",
    "24/7" and "12-3" are not "15", "247" and "123".
    """
    ch = s[i]
    if ch.isspace():
        return True
    if ch in _SIGNIFICANT_MARKS:
        return False
    if not (unicodedata.category(ch).startswith("P") or ch in _APOSTROPHE_LIKE):
        return False
    between_digits = 0 < i < len(s) - 1 and s[i - 1].isdigit() and s[i + 1].isdigit()
    return not between_digits


def _skeleton(s: str) -> str:
    """The canonical form with its punctuation and spacing taken out."""
    c = canonicalize(s)
    return "".join(ch for i, ch in enumerate(c) if not _ignorable(c, i))


def stage_a_punctuation_only(observed: str, expected: str) -> bool:
    """True when the two differ only in punctuation and spacing.

    Kept apart from the score, which is where a misread belongs: a letter the
    reader got wrong is a different kind of difference from a mark the label
    left out, and folding the two together would let a changed letter pass as
    "only punctuation".
    """
    a, b = _skeleton(observed), _skeleton(expected)
    return bool(a) and a == b and any(ch.isalnum() for ch in a)


def _run_words(s: str) -> tuple[str, ...]:
    words = normalize_words(canonicalize(s))
    return words[1:] if len(words) > 1 and words[0] in _ARTICLES else words


def stage_a_normalized(observed: str, expected: str) -> bool:
    return canonicalize(observed) == canonicalize(expected)


def stage_a_word_run(observed: str, expected: str) -> bool:
    """True when either value's whole words sit inside the other's as a run.

    Whole words, not letters, for the reason `docs/decisions.md#0007` gives for
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


# ---------------------------------------------------------------------------
# Searching the label's text for a declared name
# ---------------------------------------------------------------------------
#
# The stages above compare one reading against one name. A search compares a
# name against every line the reader read, which is hundreds of comparisons on
# one label, so a test that is safe once is not safe here: "SOUTHERN" scores
# above the pass threshold against "SOUTHERN CROSS", because Jaro-Winkler
# rewards a shared start, and a label can print both. The search routes below
# are each stricter than the stage they come from, and each says in its name
# what it found.

SEARCH_EXACT = "exact"
SEARCH_PUNCTUATION = "punctuation"
SEARCH_WITHIN = "within"
SEARCH_SHORTENED = "shortened"
SEARCH_MISREAD = "misread"

# Strongest first. A search reports the first route any line satisfies, so an
# exact line beats one that only contains the name, wherever each sits.
SEARCH_ROUTES = (
    SEARCH_EXACT,
    SEARCH_PUNCTUATION,
    SEARCH_WITHIN,
    SEARCH_SHORTENED,
    SEARCH_MISREAD,
)


def shortened(name: str, trailing: frozenset[str]) -> tuple[str, ...]:
    """The name's words with its trailing business and class words dropped.

    "VIKRE DISTILLERY" is "VIKRE", "THREE DOCTORS BOURBON" is "THREE DOCTORS".
    Only trailing words go, and only the ones `trailing` lists, so a name is
    never cut in its middle. Empty when nothing was dropped or nothing is left.
    """
    words = list(_run_words(name))
    full = len(words)
    while words and words[-1] in trailing:
        words.pop()
    return tuple(words) if 0 < len(words) < full else ()


def search_route(
    line: str,
    name: str,
    *,
    trailing: frozenset[str],
    min_length: int,
    within_min_length: int,
    misread_min_length: int,
) -> str | None:
    """Which search route finds `name` in one line of the label, or None.

    Lengths count the letters and digits of the name once punctuation and
    spacing are out, because that is what a reader can get wrong.

      exact        — the line is the name, once normalised.
      punctuation  — the line is the name once punctuation and spacing are out.
      within       — the name's whole words sit in the line as a run, and the
                     name is at least `within_min_length` long or two words: a
                     short one-word name is a word in any sentence.
      shortened    — the line is the name less its trailing business and class
                     words, whole: a shortened name is often a place or a
                     common word, so it only counts as a line of its own.
      misread      — the line is the name, or its shortened form, with one
                     character different, and that name is at least
                     `misread_min_length` long, so one character is a small
                     part of it.

    A name shorter than `min_length` is not searched for at all.
    """
    target = _skeleton(name)
    if len(target) < min_length:
        return None
    if stage_a_normalized(line, name):
        return SEARCH_EXACT
    seen = _skeleton(line)
    if seen == target:
        return SEARCH_PUNCTUATION
    name_words = _run_words(name)
    if (len(name_words) >= 2 or len(target) >= within_min_length) and word_run_present(
        _run_words(line), name_words
    ):
        return SEARCH_WITHIN
    short = shortened(name, trailing)
    short_target = "".join(short)
    if len(short_target) >= min_length and seen == short_target:
        return SEARCH_SHORTENED
    for form in (target, short_target):
        if len(form) >= misread_min_length and Levenshtein.distance(seen, form) <= 1:
            return SEARCH_MISREAD
    return None
