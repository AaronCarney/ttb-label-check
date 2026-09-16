"""Shared helpers for validator implementations.

These were originally co-located in `equality_match.py` and imported by every
sibling validator, which created a silent load-order coupling: every validator
file depended on `equality_match` being importable first. Moving them to a
private `_helpers` module makes the relationship explicit and matches Python
conventions for internal package utilities (underscore prefix on the module).

`equality_match.py` retains `_normalize` because it is genuinely equality-
internal (only `equality_match` and `enumerated_match` use NFKC + casefold
comparison).

The orphan-validator check (`test_every_validator_module_registers_at_least_one_name`)
walks `app/rules/_validators/*.py` and asserts each file registers ≥ 1 name.
That check skips any module whose name starts with `_` (including `__init__.py`
and `_helpers.py`) so private utility modules do not falsely trip the gate.
"""
from __future__ import annotations

import re
import unicodedata

from app.rules._validators import ValidatorContext
from app.schemas.extracted import FieldObservation
from app.schemas.rejection import EngineMeta
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
    parts = [str(value[k]).strip() for k in keys if value.get(k) not in (None, "")]
    return ", ".join(p for p in parts if p)


# Comparing a label reading with an application value is comparing two ways of
# writing the same thing. Both get reduced to a list of plain words first, so
# case, punctuation, accents and spacing stop mattering — which is what the
# brief asks for when it calls "STONE'S THROW" and "Stone's Throw" the same
# value. One spelling pair is folded together on top of that, because the
# regulations permit either spelling and the registry and the label routinely
# differ on it: whisky reads as whiskey.
_SPELLING_VARIANTS = {"whisky": "whiskey", "whiskies": "whiskey"}


def normalize_words(text: str) -> tuple[str, ...]:
    """One value reduced to its plain words, in order.

    Accents are folded away, the ampersand is spelled out, everything that is
    not a letter or a digit becomes a break, and each word is lowercased.
    """
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = folded.replace("&", " and ")
    words = re.split(r"[^0-9a-zA-Z]+", folded.lower())
    return tuple(_SPELLING_VARIANTS.get(w, w) for w in words if w)


def word_run_present(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    """True when `needle` appears inside `haystack` as consecutive whole words.

    Whole words, not letters: "gin" must not match inside "Virginia".
    """
    if not needle or len(needle) > len(haystack):
        return False
    return any(
        haystack[i:i + len(needle)] == needle
        for i in range(len(haystack) - len(needle) + 1)
    )


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
