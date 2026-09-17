"""Shared helpers for validator implementations.

These were originally co-located in `equality_match.py` and imported by every
sibling validator, which created a silent load-order coupling: every validator
file depended on `equality_match` being importable first. Moving them to a
private `_helpers` module makes the relationship explicit and matches Python
conventions for internal package utilities (underscore prefix on the module).

`equality_match.py` retains `_normalize` because it is genuinely equality-
internal (only `enumerated_match`, the one name that file still registers,
uses NFKC + casefold comparison).

The orphan-validator check (`test_every_validator_module_registers_at_least_one_name`)
walks `app/rules/_validators/*.py` and asserts each file registers ≥ 1 name.
That check skips any module whose name starts with `_` (including `__init__.py`
and `_helpers.py`) so private utility modules do not falsely trip the gate.
"""

from __future__ import annotations

import re
import unicodedata

from app.rules._validators import ValidatorContext
from app.schemas.expected import ExpectedValue
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import EngineMeta, Outcome, Severity, ValidationResult
from app.schemas.rules import RuleDefinition


def _build_meta(rule: RuleDefinition, ctx: ValidatorContext, elapsed_ms: int = 0) -> EngineMeta:
    """Construct EngineMeta from rule + per-evaluation context.

    `elapsed_ms` defaults to 0; the engine overrides it on every return path
    with the actual per-rule monotonic delta (yaml_engine._run_one).
    """
    return EngineMeta(
        engine_version=ctx.engine_version,
        rule_pack=rule.rule_pack or "unknown",
        rule_pack_version=rule.rule_pack_version or "0.0.0",
        started_at_ms=ctx.started_at_ms,
        elapsed_ms=elapsed_ms,
    )


def _conf(obs: FieldObservation) -> float:
    """Aggregated confidence = min over evidence items, 0.0 if no evidence."""
    if not obs.evidence:
        return 0.0
    return min(ev.confidence for ev in obs.evidence)


# The reader returns a dict per field, not a bare string: `_SCHEMAS` in
# `app/vision/cloud.py` gives each field its own payload shape, and every
# payload carries a `confidence` alongside the reading itself. Text validators
# compare one string, so they need the reading pulled out of the payload. A
# validator that stringifies the whole dict compares the repr — `{'text': '…'}`
# — which matches nothing and reports a compliant label as non-compliant.
#
# This map names, per field, the payload keys that hold the reading. Both the
# reader's field ids and the rule pack's evidence names are listed, because an
# observation reaches a validator under either. Metadata keys are not listed,
# so an empty reading projects to an empty string and presence fails as it
# should.
_READING_KEYS: dict[str, tuple[str, ...]] = {
    "brand_name": ("brand_name",),
    "brand": ("brand_name",),
    "class_type": ("class_type",),
    "abv": ("abv_pct",),
    "alc_text": ("abv_pct",),
    "alcohol_content": ("abv_pct",),
    "net_contents": ("net_contents_value",),
    "gov_warning": ("text",),
    "warning_block": ("text",),
    "government_warning": ("text",),
    "name_address": ("name", "city", "state"),
    "bottler": ("name", "city", "state"),
    "name_and_address": ("name", "city", "state"),
    "country_origin": ("country",),
    "country_of_origin": ("country",),
}

# Keys that describe a reading rather than being one. Excluded from the
# fallback scan so a payload holding only metadata projects to "".
_METADATA_KEYS = frozenset({"confidence", "unit", "page_id", "panel", "bbox"})


def project_reading(obs: FieldObservation) -> str:
    """The one string a text validator compares, taken from `obs.observed_value`.

    A bare string passes through, so hand-built fixtures keep working. A dict
    is reduced to the keys `_READING_KEYS` names for that field, joined with
    ", " where a field has several parts (name, city and state make up the
    name-and-address element the application declares as one line). A dict for
    a field with no entry falls back to its own non-metadata keys.
    """
    value = obs.observed_value
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return str(value)
    keys = _READING_KEYS.get(obs.field_id)
    if keys is None:
        keys = tuple(k for k in value if k not in _METADATA_KEYS)
    # The None check is load-bearing: str(None) is "None", which is truthy and
    # would reach a reviewer as the reading for a key the reader left unset. An
    # empty or whitespace-only value needs no check here - it strips to "" and
    # the join drops it.
    parts = [str(value[k]).strip() for k in keys if value.get(k) is not None]
    return ", ".join(p for p in parts if p)


# Comparing a label reading with an application value is comparing two ways of
# writing the same thing. Both get reduced to a list of plain words first, so
# case, punctuation, accents and spacing stop mattering — which is what the
# brief asks for when it calls "STONE'S THROW" and "Stone's Throw" the same
# value. On top of that, a token is rewritten to the one spelling the
# comparison uses. Whisky reads as whiskey, because the regulations permit
# either spelling and the registry and the label routinely differ on it. The
# ampersand reads as "and", because it is a way of writing that word rather
# than punctuation, and this table is where "this writing means that word"
# belongs.
_SPELLING_VARIANTS = {"whisky": "whiskey", "whiskies": "whiskey", "&": "and"}


def normalize_words(text: str) -> tuple[str, ...]:
    """One value reduced to its plain words, in order.

    Accents are folded away, each word is lowercased, and everything that is
    not a letter or a digit becomes a break. The ampersand is the exception: it
    comes through the break as its own token, so `_SPELLING_VARIANTS` spells it
    out alongside every other word that has two writings.
    """
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    words = re.findall(r"[0-9a-z]+|&", folded.lower())
    return tuple(_SPELLING_VARIANTS.get(w, w) for w in words)


def word_run_present(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    """True when `needle` appears inside `haystack` as consecutive whole words.

    Whole words, not letters: "gin" must not match inside "Virginia".
    """
    if not needle or len(needle) > len(haystack):
        return False
    return any(haystack[i : i + len(needle)] == needle for i in range(len(haystack)))


def first_number(value: object) -> float | None:
    """The first number in a reading, whether it arrived as one or as text."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    match = re.search(r"[0-9]+(?:\.[0-9]+)?", str(value))
    return float(match.group()) if match else None


# --- the element the reader did not find -------------------------------------
#
# A field a reader could not read and a field a label does not carry reach a
# validator in the same shape: an observation whose reading is empty. Every
# validator used to treat the pair as one thing and reject the label for both,
# which rewards a reader for guessing. On a compliant label, a garbled `[OSTL`
# for `LOST LANTERN` reaches a reviewer and an honest empty reading is a
# rejection, which is the wrong way round: the guess is the answer that costs a
# reviewer most, because it is wrong beside a field they have no reason to
# re-check.
#
# The two are told apart by the evidence, not by the value. Both readers attach
# one `Evidence` per field carrying the box the value was read from and the text
# they read there (`app/vision/local.py`, `app/vision/cloud.py`), and a field
# neither reader located carries neither. So an empty reading with no box and no
# extracted text is the reader saying "I did not find this on the label" - which
# is not the claim "this label does not carry it", and must not be reported as
# though it were.
#
# What that distinction means for one rule is the rule pack's to decide, not
# this module's, and it is decided on how reliably the reader finds that element.
# For the government warning the reader is measured at 30 of 30 over the corpus
# (`plans/wave3-R.md`), so not finding it is evidence it is absent and that rule
# sets `unlocated_is_absent: true`. Everywhere else the default stands and the
# finding goes to a reviewer, who has the label in front of them.

NOT_READ_CODE = "LEGIBILITY.FIELD.NOT_READ"


def unlocated(obs: FieldObservation, reading: str | None = None) -> bool:
    """Did the reader fail to find this element on the label at all?

    True only when the reading is empty *and* no evidence carries a box or any
    extracted text. A reading the reader produced is located even when it is
    wrong, and nothing about how a wrong reading is judged changes here.

    `reading` is for the validators that do not compare `project_reading`:
    `heading_style_check` reads the heading out of the warning payload,
    `regex_match` projects the label's own alcohol wording, and
    `same_field_of_vision_check` reads a panel map. Asking the generic
    projection about those would call a field the reader found "not found",
    because the projection looks for a key the payload does not carry.
    """
    if (project_reading(obs) if reading is None else reading).strip():
        return False
    return not any(ev.bbox is not None or (ev.extracted_text or "").strip() for ev in obs.evidence)


def unlocated_is_absent(rule: RuleDefinition) -> bool:
    """May this rule read "the reader did not find it" as "the label lacks it"?

    Off unless the pack says otherwise, so a rule that has not thought about it
    sends the reviewer a question rather than issuing a rejection nobody checked.
    """
    return bool(rule.parameters.get("unlocated_is_absent"))


# What each field is called in the sentence a reviewer reads. A validator that
# serves many fields - presence_check, equality_match - cannot name the element
# from its own arguments, and said "this element", which tells a reviewer
# nothing they can act on: they are looking at a list of findings and have to
# work out which line of the label each one is about. The observation knows the
# field, so the sentence can say it.
_ELEMENT_NAMES = {
    "brand_name": "a brand name",
    "class_type": "a class or type designation",
    "abv": "an alcohol content statement",
    "net_contents": "a net contents statement",
    "gov_warning": "the government warning",
    "name_address": "a name and address",
    "country_origin": "a country of origin statement",
}


def element_name(obs: FieldObservation) -> str:
    """The words for the element this observation is about.

    Falls back to "this element" only for a field_id the table does not carry,
    which is the honest answer when nothing here knows what it was.
    """
    return _ELEMENT_NAMES.get(obs.field_id, "this element")


def not_read_result(
    obs: FieldObservation,
    exp: ExpectedValue,
    rule: RuleDefinition,
    ctx: ValidatorContext,
    *,
    element: str | None = None,
) -> ValidationResult:
    """The finding for an element the reader did not find: a reviewer's to settle.

    `element` names it in the sentence. A validator that serves one element
    passes its own words; one that serves many leaves it out and the name comes
    from the observation's field, so no reviewer is told "this element".

    `INSUFFICIENT_EVIDENCE` and `warn`, whatever severity the rule carries, so
    `app/services/disposition.py` routes it to `needs_review` and it cannot
    reject the submission on its own.
    """
    element = element or element_name(obs)
    return ValidationResult(
        rule_id=rule.rule_id,
        cfr_citation=rule.cfr_citation,
        beverage_class=obs.beverage_class,
        outcome=Outcome.INSUFFICIENT_EVIDENCE,
        severity=Severity.WARN,
        reason_code=NOT_READ_CODE,
        aggregated_confidence=_conf(obs),
        evidence=obs.evidence,
        expected=exp,
        observed=obs,
        engine_meta=_build_meta(rule, ctx),
        message=(
            f"The reader did not find {element} on this label, so this check was "
            "not made. That is not a finding that the label lacks it: compare the "
            "label against the application yourself."
        ),
    )
