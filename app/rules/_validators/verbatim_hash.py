"""verbatim_hash validator: sha256 of canonicalized observed text vs. asset hash.

Canonicalization ops are taken from ``rule.asset or {}`` (a list of
op names, applied in order). When the rule declares no asset block (e.g.,
unit tests using ``make_rule``), the default op list applies. The loader
(``_load_assets``) imports ``canonicalize_text`` from this module and
runs the SAME op pipeline before hashing the asset bytes, so loader and
validator produce identical hashes, which the loader cross-checks.

What the canonical form throws away, and why it throws away exactly that:
the mandated statement fixes the words, the numbers and the punctuation. It
does not fix the letter case of the statement's body — the separate heading
rule is what requires the heading's capitals — and it does not fix how the
printer spaced or broke the lines. So the canonical form folds case, joins a
word a line break split with a hyphen, and takes every space out. A label that
prints "GOVERNMENT WARNING  :", one that prints "GOVERNMENT WARNING:(1)" and a
reading that runs "IMPAIRSYOUR" together all reach the same canonical string
as the regulation's own text; a label that prints a different word or letter,
or ends the statement with a quotation mark instead of a full stop, does not.

Spaces are removed rather than collapsed because label type is justified,
which closes some word gaps and opens others, and because the reader loses a
narrow gap as readily as a printer closes one. Removing them cannot make a
different statement equal the mandated one: the letters, digits and
punctuation still have to match in order.

Supported ops: ``nfkc``, ``join_line_break_hyphens``, ``drop_whitespace``,
``casefold``. There is no op for quotation marks: the mandated statement
contains none, so a label that prints one, curly or straight, differs from it
either way.

A difference is not always the label's. Measured over the corpus, 11 of the
15 warnings this check found different were the reader's misreads of a correct
label: an accent added to a letter, ``(I)`` for ``(1)``, ``ORINK`` for
``DRINK``, one punctuation mark added, dropped or swapped. The reader's own
confidence does not tell those from the true differences at any granularity,
so the kind of difference has to. Where every difference is of a kind the
reader is measured to invent, the product cannot say whether the label or the
reading is at fault, and FR-9 makes that needs review; the finding names each
difference so the reviewer checks those spots on the label. A letter or a word
added, dropped or changed any other way is not a kind the reader invents, and
stays a mismatch.

Folding case cannot let a lower-case "surgeon general" through as a match:
TTB's checklists ask whether its S and G are capitals. A reading that shows
either in lower case is needs review, because a reader that confuses s with S
is not evidence the label prints it.
"""

from __future__ import annotations

import difflib
import hashlib
import re
import unicodedata
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from app.rules._validators import ValidatorContext, register
from app.rules._validators._helpers import (
    _build_meta,
    _conf,
    heading_not_read_result,
    not_read_result,
    project_reading,
    unlocated,
    unlocated_is_absent,
    verdict_result,
)
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import Outcome, Severity, ValidationResult
from app.schemas.rules import AssetRef, RuleDefinition

DEFAULT_NORMALIZATION_OPS: tuple[str, ...] = (
    "nfkc",
    "join_line_break_hyphens",
    "drop_whitespace",
    "casefold",
)

NOT_CONFIRMED_CODE = "WARNING.VERBATIM.NOT_CONFIRMED"

# A hyphen with whitespace after it is a word a line break split. The mandated
# statement contains no hyphen of its own, so nothing legitimate is joined here.
_LINE_BREAK_HYPHEN = re.compile(r"-\s+")


def canonicalize_text(s: str, ops: Sequence[str] = DEFAULT_NORMALIZATION_OPS) -> str:
    """Apply normalization ops in declaration order. Loader and validator MUST
    use this same helper so verbatim hashes match.
    Raises ValueError on an unknown op name (fail-closed).
    """
    for op in ops:
        if op == "nfkc":
            s = unicodedata.normalize("NFKC", s)
        elif op == "join_line_break_hyphens":
            s = _LINE_BREAK_HYPHEN.sub("", s)
        elif op == "drop_whitespace":
            s = re.sub(r"\s+", "", s)
        elif op == "casefold":
            s = s.casefold()
        else:
            raise ValueError(f"unknown normalization op: {op!r}")
    return s


@register("verbatim_hash")
def verbatim_hash(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
) -> ValidationResult:
    # The warning's words were read and its heading was not.
    heading_not_read = heading_not_read_result(obs, exp, rule, ctx)
    if heading_not_read is not None:
        return heading_not_read

    # The reader did not find this on the label. That is a question for a
    # reviewer, not a rejection - see `unlocated` in `_helpers.py`.
    if unlocated(obs) and not unlocated_is_absent(rule):
        return not_read_result(obs, exp, rule, ctx, element="the government warning")

    key = rule.parameters.get("asset_key")
    asset = ctx.assets.get(key) if key else None
    ops = (rule.asset or {}).get("normalization", DEFAULT_NORMALIZATION_OPS)
    # The warning body, not the repr of the payload that carries it:
    # `str(obs.observed_value)` on the reader's dict hashes "{'text': …}" and
    # can never equal the hash of the asset text.
    reading = project_reading(obs)
    observed = canonicalize_text(reading, ops=ops)
    matched = (
        asset is not None and hashlib.sha256(observed.encode("utf-8")).hexdigest() == asset.sha256
    )
    if matched:
        lowered = _lower_case_surgeon_general(reading)
        if lowered:
            return _needs_review(
                obs,
                exp,
                rule,
                ctx,
                f'The reading prints "{lowered}". TTB\'s checklists ask for a capital S and G '
                "in Surgeon General, and the reader can misread a capital as lower case, so "
                "check those two letters on the label.",
            )
        return verdict_result(obs, exp, rule, ctx, ok=True)

    mandated = _mandated_text(asset, ops) if asset is not None else None
    doubts = _reader_doubts(canonicalize_text(mandated, ops=ops), observed) if mandated else None
    if doubts:
        return _needs_review(
            obs,
            exp,
            rule,
            ctx,
            "The reading differs from the §16.21 statement only in ways this reader is "
            f"measured to misread a correct label: {'; '.join(doubts)}. Check "
            "those spots on the label: if the label prints them, it does not carry the "
            "statement as prescribed.",
        )
    lexicon = _word_list(rule)
    unsure = _unsure_spots(mandated, reading, ops, lexicon) if mandated and lexicon else None
    if unsure:
        return _needs_review(
            obs,
            exp,
            rule,
            ctx,
            "The reading differs from the §16.21 statement, but not in a way that shows the "
            f"label does: {'; '.join(unsure)}. Check those spots on the label: if the label "
            "prints them, it does not carry the statement as prescribed.",
        )
    return verdict_result(obs, exp, rule, ctx, ok=False)


# The repository root, which the loader anchors an asset's path to by default.
_ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=4)
def _read_asset(path: str) -> str | None:
    try:
        return (_ROOT / path).read_text(encoding="utf-8")
    except OSError:
        return None


def _mandated_text(asset: AssetRef, ops: Sequence[str]) -> str | None:
    """The statement itself, used only once no hash matched, to say where the
    reading differs. It is trusted only if it hashes to the pin the loader
    checked; otherwise the comparison falls back to a plain mismatch."""
    text = _read_asset(asset.path)
    if text is None:
        return None
    digest = hashlib.sha256(canonicalize_text(text, ops=ops).encode("utf-8")).hexdigest()
    return text if digest == asset.sha256 else None


# Glyphs the reader is measured to swap on a correct label, after case folding:
# (1) read as (I), DRINK read as ORINK. Each set holds shapes that look alike
# in the capitals most warnings are printed in.
_LOOKALIKES = (frozenset("1il|"), frozenset("0od"))

# Glyphs a single narrow stroke makes. The reader adds one inside a word where
# two letters sit close ("heailth" for "health") and loses one where a letter
# is thin ("alcohoic").
_THIN_GLYPHS = frozenset("1il|")


def _base_letter(ch: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))


def _reader_prone(expected: str, read: str) -> bool:
    """Is this one difference a kind the reader is measured to invent?"""
    if len(expected) <= 1 and len(read) <= 1 and not any(c.isalnum() for c in expected + read):
        return True  # one punctuation mark added, dropped or swapped for another
    if len(expected) != len(read) or not expected:
        return False
    for e, r in zip(expected, read, strict=True):
        if e == r or _base_letter(e) == _base_letter(r) != r:
            continue  # the same letter, or it with an accent the label lacks
        if any(e in group and r in group for group in _LOOKALIKES):
            continue
        if not e.isalnum() and not r.isalnum():
            # One mark swapped for another. The matcher joins neighbouring
            # differences into one span, so "(I]" for "(1)" arrives as a single
            # difference made of a lookalike and a swapped bracket, each of
            # which is a misread on its own.
            continue
        return False
    return True


def _thin_glyph_in_a_word(text: str, start: int, end: int) -> bool:
    """Is text[start:end] one thin glyph with a letter on either side of it?"""
    return (
        end - start == 1
        and text[start] in _THIN_GLYPHS
        and start > 0
        and end < len(text)
        and text[start - 1].isalpha()
        and text[end].isalpha()
    )


def _reader_doubts(expected: str, observed: str) -> list[str] | None:
    """Each difference, described for a reviewer, when every one of them is a
    kind the reader invents; None when any is not, which leaves a mismatch.

    Three kinds are judged by where they fall rather than by the characters
    alone: a thin glyph added or dropped inside a word, and text after the
    statement's last words, which is the block running on into the next line
    printed under it rather than a change to the statement."""
    doubts: list[str] = []
    for i1, i2, j1, j2 in _differences(expected, observed):
        doubt = _prone_doubt(expected, observed, i1, i2, j1, j2)
        if doubt is None:
            return None
        doubts.append(doubt)
    return doubts or None


def _differences(expected: str, observed: str) -> list[tuple[int, int, int, int]]:
    matcher = difflib.SequenceMatcher(None, expected, observed, autojunk=False)
    return [(i1, i2, j1, j2) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]


def _prone_doubt(expected: str, observed: str, i1: int, i2: int, j1: int, j2: int) -> str | None:
    """One difference described for a reviewer, when it is a kind the reader
    invents; None when it is not."""
    want, got = expected[i1:i2], observed[j1:j2]
    where = observed[max(0, j1 - 8) : j2 + 8]
    if got and (i1 == len(expected) or (i2 == len(expected) and _reader_prone(want, ""))):
        # After the statement ends, or its closing mark dropped and text
        # after it.
        return f'text after the statement\'s last words, "{got[:40]}"'
    if not want and _thin_glyph_in_a_word(observed, j1, j2):
        return f'"{got}" added in "{where}"'
    if not got and _thin_glyph_in_a_word(expected, i1, i2):
        return f'"{want}" missing in "{where}"'
    if not _reader_prone(want, got):
        return None
    if not want:
        return f'"{got}" added in "{where}"'
    if not got:
        return f'"{want}" missing in "{where}"'
    return f'"{got}" for "{want}" in "{where}"'


# A word, as the reading and the statement are split into them: each piece of
# a whitespace-separated token between marks, so "machinery,5" is "machinery"
# and "5".
_PIECE = re.compile(r"[^\W_]+")

# The two words of one letter English has. Every other letter the word list
# carries is there as the name of a letter, which a printed statement never
# uses as a word.
_ONE_LETTER_WORDS = frozenset({"a", "i"})


def _words(text: str, ops: Sequence[str]) -> tuple[str, list[tuple[int, int, str]]] | None:
    """The canonical form of `text`, with where each of its words lies in it.

    The canonical form drops every space, so the words are taken before that
    op and their offsets counted in the string it leaves. None where the ops
    do not allow that, which leaves the plain comparison.
    """
    spaced = canonicalize_text(text, ops=[op for op in ops if op != "drop_whitespace"])
    words, at = [], 0
    for token in spaced.split():
        words.append((at, at + len(token), token))
        at += len(token)
    joined = "".join(w for _s, _e, w in words)
    return (joined, words) if joined == canonicalize_text(text, ops=ops) else None


def _is_word(token: str, lexicon: frozenset[str], statement_numbers: frozenset[str]) -> bool:
    """Is every piece of this token a word, or a number the statement carries?"""
    for piece in _PIECE.findall(token):
        if any(c.isdigit() for c in piece):
            if piece not in statement_numbers:
                return False
        elif len(piece) == 1:
            if piece not in _ONE_LETTER_WORDS:
                return False
        elif piece not in lexicon:
            return False
    return True


def _unsure_spots(
    mandated: str, reading: str, ops: Sequence[str], lexicon: frozenset[str]
) -> list[str] | None:
    """Each spot where the reading differs and the difference does not show
    the label differs; None when any difference is a plain one-word change
    between real words and the reading lost or moved no run of words, which
    is a mismatch.

    Two kinds do not show it. A difference that leaves a word no dictionary
    holds: the statement is English, and a lookup is how misreads are told
    from real-word changes (Kukich 1992, "non-word" errors; Nguyen et al.
    2021). And a difference that loses, adds or moves more than one word,
    which is the reader losing a line or taking a block's lines out of order.
    Either can also be a misprint; a reviewer settles it, which is what FR-9
    asks of a difference the product cannot defend. docs/decisions.md#0063.
    """
    expected_words = _words(mandated, ops)
    observed_words = _words(reading, ops)
    if expected_words is None or observed_words is None:
        return None
    expected, e_words = expected_words
    observed, o_words = observed_words
    numbers = frozenset(p for _s, _e, w in e_words for p in _PIECE.findall(w) if p.isdigit())
    spots: list[str] = []
    changes: list[str] = []
    rearranged = False
    for i1, i2, j1, j2 in _differences(expected, observed):
        doubt = _prone_doubt(expected, observed, i1, i2, j1, j2)
        if doubt is not None:
            spots.append(doubt)
            continue
        # The reading's words the difference touches; for text dropped, the
        # words either side of the gap.
        touched = [w for s, e, w in o_words if (s < j2 and e > j1) or s == j1 or e == j1]
        strange = [w for w in touched if not _is_word(w, lexicon, numbers)]
        if strange:
            spots.append(", ".join(f'"{w}"' for w in strange) + " is not an English word")
            continue
        # Words the difference reaches into, not only words it wholly covers:
        # the matcher aligns on letters, so a moved phrase arrives with its
        # edges shifted into the words beside it.
        lost = sum(1 for s, e, _w in e_words if s < i2 and e > i1)
        added = sum(1 for s, e, _w in o_words if s < j2 and e > j1)
        if lost > 1 or added > 1:
            what = observed[j1:j2] or expected[i1:i2]
            spots.append(f'several words lost, added or moved at "{what[:40]}"')
            rearranged = True
            continue
        changes.append(f'"{observed[j1:j2]}" for "{expected[i1:i2]}"')
    # Where the reader lost or moved words, aligning what is left letter by
    # letter leaves small differences between real words that the moved text
    # made, so a one-word change beside them is not shown to be the label's.
    if changes and not rearranged:
        return None
    return spots + changes or None


def _word_list(rule: RuleDefinition) -> frozenset[str] | None:
    """The English word list the rule pack names, checked against its pin."""
    path = rule.parameters.get("word_list")
    pin = rule.parameters.get("word_list_sha256")
    if not path or not pin:
        return None
    return _load_word_list(str(path), str(pin))


@lru_cache(maxsize=2)
def _load_word_list(path: str, pin: str) -> frozenset[str]:
    """The words of a SCOWL list, below the licence header its `---` line ends.

    A file that does not hash to the pin is refused rather than used: a
    different list would change which differences reject a label."""
    data = (_ROOT / path).read_bytes()
    if hashlib.sha256(data).hexdigest() != pin:
        raise ValueError(f"word list {path} does not match its pin")
    _header, _rule, body = data.decode("utf-8").partition("\n---\n")
    return frozenset(line.strip().casefold() for line in body.splitlines() if line.strip())


_SURGEON_GENERAL = re.compile(r"surgeon\s*general", re.IGNORECASE)


def _lower_case_surgeon_general(reading: str) -> str | None:
    """The words as read, when either initial is lower case."""
    found = _SURGEON_GENERAL.search(unicodedata.normalize("NFKC", reading))
    if found is None:
        return None
    words = found.group()
    initials = (words[0], words[len(words) - len("general")])
    return words if any(c.islower() for c in initials) else None


def _needs_review(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
    message: str,
) -> ValidationResult:
    """Insufficient evidence at warn, which `app/services/disposition.py` routes
    to needs review whatever severity the rule carries."""
    return ValidationResult(
        rule_id=rule.rule_id,
        cfr_citation=rule.cfr_citation,
        beverage_class=obs.beverage_class,
        outcome=Outcome.INSUFFICIENT_EVIDENCE,
        severity=Severity.WARN,
        reason_code=NOT_CONFIRMED_CODE,
        aggregated_confidence=_conf(obs),
        evidence=obs.evidence,
        expected=exp,
        observed=obs,
        engine_meta=_build_meta(rule, ctx),
        message=message,
    )
